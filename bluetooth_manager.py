import asyncio
import logging
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

# Konfigurer logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("BluetoothManager")

# --- VIGTIGT: Opdater disse værdier til dit projekt ---
TARGET_DEVICE_NAME = "ESP32"  # Navnet på din ESP32 enhed
SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
LED_CHARACTERISTIC_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"


class BluetoothManager:
    """
    BluetoothManager til at kommunikere med ESP32 via BLE.
    Holder én enkelt forbindelse og en kommando-queue kørende i baggrunden.
    """

    def __init__(self, device_name: str):
        self.device_name = device_name
        self.client: Optional[BleakClient] = None
        self.command_queue = asyncio.Queue()
        self._is_connected = False
        self._disconnected_event = asyncio.Event()

    async def _process_command_queue(self):
        logger.info("[BLE] Command queue processor started.")
        while self._is_connected and self.client and self.client.is_connected:
            try:
                command = await self.command_queue.get()
                if command is None:
                    break
                logger.info(f"[BLE] → '{command}'")
                await self.client.write_gatt_char(
                    LED_CHARACTERISTIC_UUID,
                    command.encode("utf-8")
                )
                self.command_queue.task_done()
            except Exception as e:
                logger.error(f"[BLE][ERROR] Fejl i command queue: {e}")
                break
        logger.info("[BLE] Command queue processor stopped.")

    def _on_disconnect(self, client: BleakClient):
        logger.warning(f"[BLE] Afbrudt fra {client.address}")
        self._is_connected = False
        self.client = None
        # Tøm queue, så gamle kommandoer ikke ligger og blokerer
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
                self.command_queue.task_done()
            except Exception:
                pass
        self._disconnected_event.set()

    async def send_command(self, command: str):
        if not command.strip():
            logger.warning("[BLE] Forsøg på at sende tom kommando. Ignoreres.")
            return
        if not self._is_connected:
            logger.warning(f"[BLE] Ikke forbundet. Kommando droppet: '{command}'")
            return
        logger.debug(f"[BLE] Køer kommando: '{command}'")
        await self.command_queue.put(command)

    async def run(self):
        backoff = 5  # startværdi for retry-delay
        while True:
            logger.info(f"[BLE] Scanner efter enhed '{self.device_name}'...")
            device: Optional[BLEDevice] = await BleakScanner.find_device_by_name(
                self.device_name, timeout=10.0
            )

            if not device:
                logger.warning(f"[BLE] Enhed '{self.device_name}' ikke fundet. Prøver igen om {backoff} sek...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)  # exponential backoff op til 1 minut
                continue

            logger.info(f"[BLE] Fundet enhed: {device.name} ({device.address})")
            self._disconnected_event.clear()

            try:
                async with BleakClient(device, disconnected_callback=self._on_disconnect) as client:
                    if client.is_connected:
                        logger.info(f"[BLE] Forbundet til {device.address}")
                        self.client = client
                        self._is_connected = True
                        backoff = 5  # reset backoff ved succes

                        queue_processor_task = asyncio.create_task(self._process_command_queue())
                        await self._disconnected_event.wait()
                        await self.command_queue.put(None)
                        await queue_processor_task
            except Exception as e:
                logger.error(f"[BLE][ERROR] Forbindelse fejlede: {e}")
                self._is_connected = False
                self.client = None
                logger.info(f"[BLE] Prøver igen om {backoff} sek...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)


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
