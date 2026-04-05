import asyncio
import logging
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from config import (
    BLE_DEVICE_NAME as TARGET_DEVICE_NAME,
    BLE_LED_CHARACTERISTIC_UUID as LED_CHARACTERISTIC_UUID,
    BLE_RECONNECT_BACKOFF_MAX,
    BLE_RECONNECT_BACKOFF_MIN,
    BLE_SERVICE_UUID as SERVICE_UUID,
)

logger = logging.getLogger(__name__)

# Hvor ofte watchdog tjekker om forbindelsen stadig lever (sekunder)
_WATCHDOG_INTERVAL = 2.0
# Hvor ofte en keepalive-read sendes ved inaktivitet (sekunder).
# Beskytter mod ESP32 NimBLE idle-disconnect.
_KEEPALIVE_INTERVAL = 4.0


class BluetoothManager:
    """
    Robust BLE manager med:
    - Adresse-caching: forbinder via cachet adresse efter første opdagelse
      (undgår gentagne BLE-scans som kan forstyrre forbindelsen).
    - Watchdog-task: poller client.is_connected hvert 2. sek som sikkerhedsnet
      i tilfælde af at _on_disconnect ikke kaldes pålideligt (BlueZ-bug).
    - Keepalive: læser Generic Access device-name hvert 4. sek ved inaktivitet
      for at forhindre ESP32 NimBLE idle-timeout.
    - Hurtig genforbindelse efter disconnect (1 sek pause, ikke fuld backoff).
    - Backoff bruges kun når enheden slet ikke kan findes.

    VIGTIGT: asyncio.Queue og asyncio.Event oprettes i run() saa de er bundet
    til det korrekte event loop (BLE daemon-traad). Oprettes de ved import-tid
    i main thread, fejler de i Python 3.10+.
    """

    def __init__(self, device_name: str):
        self.device_name = device_name
        self.client: Optional[BleakClient] = None
        self._is_connected = False
        self._cached_address: Optional[str] = None  # Gemmes efter første fund
        # Oprettes i run() — ikke her
        self.command_queue: Optional[asyncio.Queue] = None
        self._disconnected_event: Optional[asyncio.Event] = None

    # ------------------------------------------------------------------ #
    #  Enhedsopdagelse                                                     #
    # ------------------------------------------------------------------ #

    async def _find_device(self) -> Optional[BLEDevice]:
        """
        Prøver cachet adresse først (hurtigt, ingen scan).
        Falder tilbage til navne-scan ved første kørsel eller hvis cachet
        adresse ikke svarer.
        """
        if self._cached_address:
            logger.info(f"[BLE] Forbinder via cachet adresse {self._cached_address}...")
            dev = await BleakScanner.find_device_by_address(
                self._cached_address, timeout=5.0
            )
            if dev:
                return dev
            logger.warning("[BLE] Cachet adresse ikke fundet — scanner efter navn...")
            self._cached_address = None  # Ugyldiggør cache

        logger.info(f"[BLE] Scanner efter '{self.device_name}'...")
        device = await BleakScanner.find_device_by_name(self.device_name, timeout=10.0)
        if device:
            self._cached_address = device.address
            logger.info(
                f"[BLE] Fundet {device.name} @ {device.address} (adresse cachet)"
            )
        return device

    # ------------------------------------------------------------------ #
    #  Disconnect-callback                                                 #
    # ------------------------------------------------------------------ #

    def _on_disconnect(self, client: BleakClient):
        # Ignorer stale callbacks fra tidligere forbindelser.
        # BleakClient-objektet fra forrige cyklus kan stadig kalde tilbage
        # lang tid efter vi er genforbundet — det ville forgifte ny forbindelse.
        if client is not self.client:
            logger.debug(f"[BLE] Ignorerer stale disconnect-callback fra {client.address}")
            return
        # Ignorer duplikate disconnect-callbacks (BlueZ kan sende dem to gange)
        if not self._is_connected:
            logger.debug(f"[BLE] Ignorerer duplikat disconnect-callback fra {client.address}")
            return
        logger.warning(f"[BLE] Afbrudt fra {client.address}")
        self._is_connected = False
        self.client = None
        # Signalér disconnect til run()-løkken
        if self._disconnected_event and not self._disconnected_event.is_set():
            self._disconnected_event.set()

    # ------------------------------------------------------------------ #
    #  Watchdog                                                            #
    # ------------------------------------------------------------------ #

    async def _watchdog(self, client: BleakClient):
        """
        Poller client.is_connected hvert _WATCHDOG_INTERVAL sek.
        Sikkerhedsnet: hvis _on_disconnect aldrig kaldes (BlueZ-bug),
        opdager watchdog stadig disconnect og signalerer run()-loopet.
        """
        while True:
            await asyncio.sleep(_WATCHDOG_INTERVAL)
            if not client.is_connected:
                logger.warning("[BLE] Watchdog: forbindelsen mistet!")
                self._is_connected = False
                self.client = None
                if self._disconnected_event and not self._disconnected_event.is_set():
                    self._disconnected_event.set()
                break

    # ------------------------------------------------------------------ #
    #  Kommando-queue processor                                            #
    # ------------------------------------------------------------------ #

    async def _process_command_queue(self, client: BleakClient):
        """
        Sender kommandoer fra queue til ESP32.
        Sender keepalive-read ved inaktivitet for at forhindre ESP32 idle-disconnect.
        """
        logger.info("[BLE] Command queue processor startet")
        loop = asyncio.get_event_loop()
        last_activity = loop.time()

        while self._is_connected and client.is_connected:
            idle = loop.time() - last_activity
            wait = max(0.2, _KEEPALIVE_INTERVAL - idle)

            try:
                command = await asyncio.wait_for(self.command_queue.get(), timeout=wait)
                if command is None:
                    break
                logger.info(f"[BLE] → '{command}'")
                await client.write_gatt_char(
                    LED_CHARACTERISTIC_UUID,
                    command.encode("utf-8"),
                    response=False,  # Vent ikke på GATT-bekræftelse — ESP32 svarer ikke altid
                )
                self.command_queue.task_done()
                last_activity = loop.time()

            except asyncio.TimeoutError:
                if not client.is_connected:
                    break
                # Send keepalive-read af Generic Access device name (handle 0x0003).
                # Holder BLE-linket aktivt og forhindrer ESP32 NimBLE idle-timeout.
                if loop.time() - last_activity >= _KEEPALIVE_INTERVAL:
                    try:
                        await client.read_gatt_char(0x0003)
                        last_activity = loop.time()
                        logger.debug("[BLE] Keepalive OK")
                    except Exception as ka_err:
                        logger.warning(f"[BLE] Keepalive fejlede: {ka_err} — genforbinder")
                        break

            except Exception as e:
                logger.error(f"[BLE] Fejl i command queue: {e}")
                break

        logger.info("[BLE] Command queue processor stoppet")

    # ------------------------------------------------------------------ #
    #  Offentlig API                                                       #
    # ------------------------------------------------------------------ #

    async def send_command(self, command: str):
        if not command.strip():
            return
        if not self._is_connected or self.command_queue is None:
            logger.warning(f"[BLE] Ikke forbundet. Kommando droppet: '{command}'")
            return
        await self.command_queue.put(command)

    # ------------------------------------------------------------------ #
    #  Hoved-forbindelsesloop                                              #
    # ------------------------------------------------------------------ #

    async def _reset_adapter(self) -> None:
        """
        Nulstil BlueZ HCI-adapter ved opstart for at rydde stale forbindelsestilstande.
        Uden reset tror BlueZ (og ESP32) ofte de er forbundet fra forrige session,
        hvilket giver øjeblikkelige disconnects i de første par forbindelsesforsøg.
        """
        logger.info("[BLE] Nulstiller Bluetooth-adapter (rydder stale state)...")
        try:
            proc = await asyncio.create_subprocess_exec(
                "sudo", "hciconfig", "hci0", "reset",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            await asyncio.sleep(1.5)  # Vent til adapter er klar igen
            logger.info("[BLE] Adapter nulstillet OK")
        except Exception as e:
            logger.debug(f"[BLE] Adapter reset fejlede (ignoreret): {e}")

    async def run(self):
        # Opret Queue og Event her — vi er nu i BLE daemon-traadens event loop
        self.command_queue = asyncio.Queue()
        self._disconnected_event = asyncio.Event()

        # Nulstil adapter ved opstart for at rydde stale BLE-state fra forrige session
        await self._reset_adapter()

        scan_backoff = BLE_RECONNECT_BACKOFF_MIN

        while True:
            device = await self._find_device()

            if not device:
                logger.warning(
                    f"[BLE] Enhed ikke fundet. Prøver igen om {scan_backoff}s..."
                )
                await asyncio.sleep(scan_backoff)
                scan_backoff = min(scan_backoff * 2, BLE_RECONNECT_BACKOFF_MAX)
                continue

            # Enhed fundet — nulstil backoff og ryd disconnect-event
            scan_backoff = BLE_RECONNECT_BACKOFF_MIN
            self._disconnected_event.clear()

            try:
                async with BleakClient(
                    device,
                    disconnected_callback=self._on_disconnect,
                    timeout=20.0,
                ) as client:
                    if not client.is_connected:
                        logger.warning("[BLE] Forbindelsen mislykkedes — prøver igen...")
                        await asyncio.sleep(2.0)
                        continue

                    logger.info(f"[BLE] Forbundet til {device.address}")
                    self.client = client
                    self._is_connected = True

                    # Tøm køen for eventuelle gamle kommandoer og stale None
                    # poison-pills fra forrige cyklus inden vi starter processoren.
                    while not self.command_queue.empty():
                        try:
                            self.command_queue.get_nowait()
                            self.command_queue.task_done()
                        except Exception:
                            pass

                    # Start queue processor og watchdog parallelt
                    queue_task = asyncio.create_task(
                        self._process_command_queue(client)
                    )
                    watchdog_task = asyncio.create_task(self._watchdog(client))

                    # Vent på disconnect-signal (fra callback ELLER watchdog)
                    await self._disconnected_event.wait()

                    # Ryd op: cancel begge tasks (ingen poison pill — undgår stale None)
                    queue_task.cancel()
                    watchdog_task.cancel()
                    for t in (queue_task, watchdog_task):
                        try:
                            await t
                        except (asyncio.CancelledError, Exception):
                            pass

                    self._disconnected_event.clear()

            except Exception as e:
                logger.error(f"[BLE] Forbindelsesfejl: {e}")
                self._is_connected = False
                self.client = None

            # Kort pause før genforbindelsesforsøg (ikke fuld backoff ved disconnect)
            logger.info("[BLE] Genforbinder om 2 sekunder...")
            await asyncio.sleep(2.0)


# ==================== DELT INSTANS ====================
bluetooth_manager = BluetoothManager(TARGET_DEVICE_NAME)


# ==================== TEST KUN VED DIREKTE KØRSEL ====================
if __name__ == "__main__":
    async def test_run():
        logger.info("--- Kører bluetooth_manager.py i test-mode ---")

        asyncio.create_task(bluetooth_manager.run())
        await asyncio.sleep(15)

        if bluetooth_manager._is_connected:
            logger.info("--- Sender testkommandoer ---")
            await bluetooth_manager.send_command("WHITE_ON")
            await asyncio.sleep(2)
            await bluetooth_manager.send_command("WHITE_OFF")
            await asyncio.sleep(1)
            await bluetooth_manager.send_command("EFFECT=rainbow;RGB_BRIGHT=200")
            logger.info("--- Test afsluttet ---")
        else:
            logger.warning("[BLE] Ingen forbindelse, kunne ikke sende test-kommandoer.")

        await asyncio.sleep(30)

    try:
        asyncio.run(test_run())
    except KeyboardInterrupt:
        logger.info("Test stoppet af bruger.")
