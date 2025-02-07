import asyncio
from bleak import BleakScanner, BleakClient
import struct
import logging
from multiprocessing import Queue

# UUIDs for Heart Rate Service and Measurement Characteristic
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_CHAR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

def parse_heart_rate(data):
    flags = data[0]
    hr_format = flags & 0x01
    rr_interval_present = (flags >> 4) & 0x01

    offset = 1
    heart_rate = data[offset] if hr_format == 0 else struct.unpack_from("<H", data, offset)[0]
    offset += 1 if hr_format == 0 else 2

    rr_intervals = []
    if rr_interval_present:
        while offset + 1 < len(data):
            rr = struct.unpack_from("<H", data, offset)[0]
            rr_intervals.append(rr / 1024.0)
            offset += 2

    return heart_rate, rr_intervals

async def ble_process(adapter_index, output_queue):
    logging.info(f"Scanning for BLE devices using adapter hci{adapter_index}...")

    retry_count = 0
    max_retries = 3  # Retry limit if device is not found

    while retry_count < max_retries:
        devices = await BleakScanner.discover(adapter=adapter_index)
        polar_h10 = next((device for device in devices if device.name and "Polar H10" in device.name), None)

        if polar_h10:
            logging.info(f"Found Polar H10: {polar_h10.name}, Address: {polar_h10.address}")
            break
        else:
            retry_count += 1
            logging.warning(f"Polar H10 not found. Retry {retry_count}/{max_retries}")
            await asyncio.sleep(5)  # Wait before retrying

    if not polar_h10:
        logging.error("Polar H10 device not found after multiple attempts.")
        output_queue.put(None)
        return

    try:
        async with BleakClient(polar_h10.address, adapter=adapter_index) as client:
            if not client.is_connected:
                logging.error("Failed to connect to Polar H10.")
                output_queue.put(None)
                return

            logging.info("Connected to Polar H10.")

            def handle_hr_measurement(sender, data):
                heart_rate, rr_intervals = parse_heart_rate(data)
                output_queue.put((heart_rate, rr_intervals))

            await client.start_notify(HR_MEASUREMENT_CHAR_UUID, handle_hr_measurement)
            logging.info("Receiving heart rate and RR interval data.")

            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logging.info("BLE process cancelled.")
            finally:
                await client.stop_notify(HR_MEASUREMENT_CHAR_UUID)
                logging.info("Disconnected from Polar H10.")
                output_queue.put(None)

    except Exception as e:
        logging.error(f"BLE connection error: {e}")
        output_queue.put(None)

def start_ble_process(adapter_index, output_queue):
    try:
        asyncio.run(ble_process(adapter_index, output_queue))
    except Exception as e:
        logging.error(f"Unhandled error in BLE process: {e}")
        output_queue.put(None)
