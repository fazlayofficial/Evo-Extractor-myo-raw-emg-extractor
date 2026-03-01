# Evo-Extractor App
# Main Features: Visualization, Data collection, Vibrate myo, Battery Icon and Level, Connection Status.


# Required Imports

from bleak.backends.characteristic import BleakGATTCharacteristic
import glob
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import os
import sys
import csv
import asyncio
from bleak import BleakClient, BleakScanner
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import collections
import time
import struct


# Global Initializations

emg_data = np.zeros((8, 200))  # for EMG data storage (Visualization)
imu_data = np.zeros((6, 200))  # for IMU data storage (Visualization)
data_lock = threading.Lock()
DYNAMIC_EMG_SERVICE_UUID = None
DYNAMIC_EMG_CHAR_UUIDS = []
DYNAMIC_COMMAND_SERVICE_UUID = None
DYNAMIC_COMMAND_CHAR_UUID = None
DYNAMIC_IMU_SERVICE_UUID = None
DYNAMIC_IMU_CHAR_UUIDS = []
MYO_MAC = "E7:0D:8C:7F:69:84" # Myo MAC address
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_CHARACTERISTIC_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
DYNAMIC_BATTERY_LEVEL_CHAR_UUID = None
current_battery_level = -1  # -1 means unknown or not available
battery_update_callback = None

MYO_IDENTIFIERS = {
    "name_starts_with": "Myo",
    "known_service_uuids": [
        "d5060001-a904-deb9-4748-2c7f4a124842",
        "d5060005-a904-deb9-4748-2c7f4a124842",
        BATTERY_SERVICE_UUID
    ]
}

MYO_EMG_CHARACTERISTIC_UUIDS = [
    "d5060105-a904-deb9-4748-2c7f4a124842",
    "d5060205-a904-deb9-4748-2c7f4a124842",
    "d5060305-a904-deb9-4748-2c7f4a124842",
    "d5060405-a904-deb9-4748-2c7f4a124842"
]

MYO_COMMAND_CHARACTERISTIC_UUID = "d5060401-a904-deb9-4748-2c7f4a124842"
MYO_IMU_CHARACTERISTIC_UUID = "d5060402-a904-deb9-4748-2c7f4a124842"
waiting_for_connection_message_displayed = False
CSV_BASE_FILENAME = "myo_data" # Default CSV filename
csv_file = None
csv_writer = None
is_recording_csv = False
backend_command_connect = threading.Event()
backend_command_disconnect = threading.Event()
backend_command_stop_recording = threading.Event()
latest_emg_data = None
emg_data_queue = collections.deque(maxlen=500)
imu_data_queue = collections.deque(maxlen=500)
is_connected = False
is_connecting = False
myo_ble_client = None
connected_myo_address_for_frontend = None
frontend_connection_callback = None
csv_folder_path = None
csv_file_path = None
collected_emg_imu_data = []
is_collecting = False
backend_command_start_recording = threading.Event()
recording_name = ""
recording_duration_seconds = 0
recording_param_lock = threading.Lock()
csv_save_success = False
script_should_exit = asyncio.Event()
collected_data_lock = threading.Lock()
backend_command_vibrate = threading.Event()
vibration_duration = 3
vibration_param_lock = threading.Lock()


# Back-End Functions

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def emg_callback(sender, data):
    try:
        values = struct.unpack('16b', data)
        timestamp = time.time()
        timestamp_readable = datetime.fromtimestamp(timestamp).isoformat()
        with data_lock:
            for i in range(8):
                emg_data[i, :-1] = emg_data[i, 1:]
                emg_data[i, -1] = values[i]

        with collected_data_lock:
            current_emg_frame = [values[i] for i in range(8)]
            emg_data_queue.append({'timestamp': timestamp, 'timestamp_readable': timestamp_readable, 'emg': current_emg_frame})

    except Exception as e:
        print(f"EMG callback error: {e}")

def imu_callback(sender, data):
    try:
        if len(data) != 20:
            print(f"Unexpected IMU data length: {len(data)} bytes, expected 20")
            return

        imu_raw = struct.unpack('<10h', data)
        timestamp = time.time()
        timestamp_readable = datetime.fromtimestamp(timestamp).isoformat()

        accel_scale = 8.0 / 32768.0
        accel_data = [val * accel_scale * 1000 for val in imu_raw[4:7]] # mg

        gyro_scale = 2000.0 / 32768.0
        gyro_data = [val * gyro_scale for val in imu_raw[7:10]] # degrees/s

        with data_lock:
            for i in range(3):
                imu_data[i, :-1] = imu_data[i, 1:]
                imu_data[i, -1] = accel_data[i]
            for i in range(3):
                imu_data[i + 3, :-1] = imu_data[i + 3, 1:]
                imu_data[i + 3, -1] = gyro_data[i]

        with collected_data_lock:
            imu_data_queue.append({
                'timestamp': timestamp,
                'timestamp_readable': timestamp_readable,
                'accel_x': accel_data[0], 'accel_y': accel_data[1], 'accel_z': accel_data[2],
                'gyro_x': gyro_data[0], 'gyro_y': gyro_data[1], 'gyro_z': gyro_data[2]
            })

    except struct.error as e:
        print(f"IMU data unpacking error: {e}")
    except Exception as e:
        print(f"IMU callback error: {e}")

def get_unique_csv_filename(base_name, folder=""):
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_pattern = f"{base_name}_{timestamp_str}*.csv"

    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    existing_files = glob.glob(os.path.join(folder, filename_pattern))

    counter = 0
    while True:
        if counter == 0:
            new_filename = f"{base_name}_{timestamp_str}.csv"
        else:
            new_filename = f"{base_name}{timestamp_str}{counter}.csv"

        full_path = os.path.join(folder, new_filename)

        if not os.path.exists(full_path):
            return full_path

        counter += 1

async def set_emg_streaming_mode(client: BleakClient):
    global DYNAMIC_COMMAND_CHAR_UUID

    if not DYNAMIC_COMMAND_CHAR_UUID:
        print(f"[{time.time():.2f}] Error: COMMAND_CHAR_UUID not dynamically discovered. Cannot enable EMG streaming.")
        return

    try:
        command_bytes = bytearray([0x01, 0x03, 0x02, 0x00, 0x00])
        await client.write_gatt_char(DYNAMIC_COMMAND_CHAR_UUID, command_bytes, response=True)
        print(f"[{time.time():.2f}] Sent command to enable raw EMG streaming.")
    except Exception as command_err:
        print(f"[{time.time():.2f}] Failed to send EMG streaming command: {command_err}")
        raise

async def set_imu_streaming_mode(client: BleakClient):
    global DYNAMIC_COMMAND_CHAR_UUID

    if not DYNAMIC_COMMAND_CHAR_UUID:
        print(f"[{time.time():.2f}] Error: COMMAND_CHAR_UUID not available for IMU streaming.")
        return

    try:
        combined_command = bytearray([0x01, 0x03, 0x02, 0x01, 0x00])

        await client.write_gatt_char(DYNAMIC_COMMAND_CHAR_UUID, combined_command, response=True)
        print(f"[{time.time():.2f}] Sent combined EMG+IMU streaming command: {combined_command.hex()}")

        # Wait for command to take effect
        await asyncio.sleep(0.5)

    except Exception as e:
        print(f"[{time.time():.2f}] Failed to send IMU streaming command: {e}")
        raise

async def discover_battery_service(client: BleakClient):
    global DYNAMIC_BATTERY_LEVEL_CHAR_UUID
    DYNAMIC_BATTERY_LEVEL_CHAR_UUID = None
    found_battery_service = False

    print(f"[{time.time():.2f}] Discovering battery service...")

    for service in client.services:
        if service.uuid == BATTERY_SERVICE_UUID:
            found_battery_service = True
            print(f"[{time.time():.2f}] Found Battery Service: {service.uuid}")

            for char in service.characteristics:
                if char.uuid == BATTERY_LEVEL_CHARACTERISTIC_UUID:
                    DYNAMIC_BATTERY_LEVEL_CHAR_UUID = char.uuid
                    print(f"[{time.time():.2f}]   Found Battery Level Characteristic: {char.uuid}")
                    break
            break

    if not found_battery_service or not DYNAMIC_BATTERY_LEVEL_CHAR_UUID:
        print(f"[{time.time():.2f}] Warning: Battery service not found - battery status unavailable")

    return found_battery_service

async def monitor_battery_status():
    global current_battery_level, myo_ble_client, is_connected, battery_update_callback

    while not script_should_exit.is_set():
        if is_connected and myo_ble_client and DYNAMIC_BATTERY_LEVEL_CHAR_UUID:
            try:
                battery_data = await myo_ble_client.read_gatt_char(DYNAMIC_BATTERY_LEVEL_CHAR_UUID)
                battery_percent = int.from_bytes(battery_data, byteorder='little')

                if battery_percent != current_battery_level:
                    current_battery_level = battery_percent
                    print(f"[{time.time():.2f}] Battery level: {battery_percent}%")

                    # Update GUI via callback
                    if battery_update_callback:
                        battery_update_callback(battery_percent)

            except Exception as e:
                print(f"[{time.time():.2f}] Error reading battery: {e}")

        await asyncio.sleep(10)  # Read battery every 10 seconds

def set_battery_update_callback(callback):
    global battery_update_callback
    battery_update_callback = callback

def reset_battery_level():
    global current_battery_level
    current_battery_level = -1
    if battery_update_callback:
        battery_update_callback(-1)

async def vibrate_myo_backend(duration=3):
    global myo_ble_client, is_connected, DYNAMIC_COMMAND_CHAR_UUID

    if not is_connected or not myo_ble_client or not DYNAMIC_COMMAND_CHAR_UUID:
        print(f"[{time.time():.2f}] Cannot vibrate: Myo not connected or command characteristic not available")
        return False

    try:
        vibration_command = bytearray([0x03, 0x01, duration])
        await myo_ble_client.write_gatt_char(DYNAMIC_COMMAND_CHAR_UUID, vibration_command, response=False)
        print(f"[{time.time():.2f}] Sent vibration command (duration: {duration})")
        return True
    except Exception as e:
        print(f"[{time.time():.2f}] Failed to send vibration command: {e}")
        return False

async def discover_myo_uuids(client: BleakClient):
    global DYNAMIC_EMG_SERVICE_UUID, DYNAMIC_EMG_CHAR_UUIDS, DYNAMIC_COMMAND_SERVICE_UUID, DYNAMIC_COMMAND_CHAR_UUID, DYNAMIC_IMU_SERVICE_UUID, DYNAMIC_IMU_CHAR_UUIDS

    DYNAMIC_EMG_CHAR_UUIDS = []
    DYNAMIC_COMMAND_CHAR_UUID = None
    DYNAMIC_IMU_CHAR_UUIDS = []
    DYNAMIC_IMU_SERVICE_UUID = None

    print(f"[{time.time():.2f}] Discovering Myo services and characteristics...")

    if not client.services:
        raise RuntimeError("No services discovered after connection")

    print(f"[{time.time():.2f}] Available services:")
    for service in client.services:
        print(f"  Service: {service.uuid}")
        for char in service.characteristics:
            print(f"    Char: {char.uuid} (Properties: {char.properties})")

    emg_service = client.services.get_service("d5060005-a904-deb9-4748-2c7f4a124842")
    if emg_service:
        DYNAMIC_EMG_SERVICE_UUID = emg_service.uuid
        print(f"[{time.time():.2f}] Found EMG Service: {emg_service.uuid}")

        for char_uuid in MYO_EMG_CHARACTERISTIC_UUIDS:
            try:
                char = emg_service.get_characteristic(char_uuid)
                if char and "notify" in char.properties:
                    DYNAMIC_EMG_CHAR_UUIDS.append(char_uuid)
                    print(f"[{time.time():.2f}]   Found EMG Char: {char_uuid}")
            except Exception as e:
                print(f"[{time.time():.2f}]   EMG Char {char_uuid} not found: {e}")

    cmd_service = client.services.get_service("d5060001-a904-deb9-4748-2c7f4a124842")
    if cmd_service:
        DYNAMIC_COMMAND_SERVICE_UUID = cmd_service.uuid
        print(f"[{time.time():.2f}] Found Command Service: {cmd_service.uuid}")

        try:
            cmd_char = cmd_service.get_characteristic(MYO_COMMAND_CHARACTERISTIC_UUID)
            if cmd_char and "write" in cmd_char.properties:
                DYNAMIC_COMMAND_CHAR_UUID = cmd_char.uuid
                print(f"[{time.time():.2f}]   Found Command Char: {cmd_char.uuid}")
        except Exception as e:
            print(f"[{time.time():.2f}]   Command Char not found: {e}")

    imu_service = client.services.get_service("d5060002-a904-deb9-4748-2c7f4a124842")
    if imu_service:
        DYNAMIC_IMU_SERVICE_UUID = imu_service.uuid
        print(f"[{time.time():.2f}] Found IMU Service: {imu_service.uuid}")
        try:
            imu_char = imu_service.get_characteristic(MYO_IMU_CHARACTERISTIC_UUID)
            if imu_char and "notify" in imu_char.properties:
                DYNAMIC_IMU_CHAR_UUIDS.append(imu_char.uuid)
                print(f"[{time.time():.2f}]   Found IMU Char: {imu_char.uuid}")
        except Exception as e:
            print(f"[{time.time():.2f}]   IMU Char not found in service {imu_service.uuid}: {e}")
    else:
        print(f"[{time.time():.2f}] Warning: IMU Service d5060002-... not found.")

    if len(DYNAMIC_EMG_CHAR_UUIDS) != 4:
        raise RuntimeError(f"Expected 4 EMG characteristics, found {len(DYNAMIC_EMG_CHAR_UUIDS)}")
    if not DYNAMIC_COMMAND_CHAR_UUID:
        raise RuntimeError("Command characteristic not found")
    if not DYNAMIC_IMU_CHAR_UUIDS:
        print(f"[{time.time():.2f}] Warning: IMU characteristic not found after checking IMU service - IMU data will not be available")

    await discover_battery_service(client)
    print(f"[{time.time():.2f}] Service discovery complete")

async def connect_to_myo():
    global myo_ble_client, is_connecting, is_connected, connected_myo_address_for_frontend, waiting_for_connection_message_displayed

    if is_connecting or is_connected:
        return

    is_connecting = True
    print(f"[{time.time():.2f}] Scanning for Myo device...")
    waiting_for_connection_message_displayed = False

    device = None
    try:
        found_devices_during_scan = {}

        def detection_callback(d, ad):
            if d.address not in found_devices_during_scan:
                is_myo = False
                if d.name and d.name.startswith(MYO_IDENTIFIERS["name_starts_with"]):
                    is_myo = True
                elif ad.service_uuids:
                    for svc_uuid in MYO_IDENTIFIERS["known_service_uuids"]:
                        if svc_uuid in ad.service_uuids:
                            is_myo = True
                            break
                if is_myo:
                    found_devices_during_scan[d.address] = d
                    print(
                        f"[{time.time():.2f}] Discovered potential Myo: {d.name if d.name else 'Unnamed'} ({d.address})")

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(10)
        await scanner.stop()

        if found_devices_during_scan:
            DYNAMIC_MYO_MAC_ADDRESS = next(iter(found_devices_during_scan))
            device = found_devices_during_scan[DYNAMIC_MYO_MAC_ADDRESS]
            connected_myo_address_for_frontend = device.address
            print(
                f"[{time.time():.2f}] Found and selected Myo: {device.name if device.name else 'Unnamed'} ({device.address})")
        else:
            print(f"[{time.time():.2f}] No Myo device found after scan.")

    except Exception as scan_err:
        print(f"[{time.time():.2f}] Error during BLE scan: {scan_err}")
        is_connecting = False
        return

    if not device:
        print(f"[{time.time():.2f}] Myo device not found. Will retry on next loop iteration.")
        is_connecting = False
        return

    try:
        myo_ble_client = BleakClient(device.address, disconnected_callback=on_disconnect)
        await myo_ble_client.connect()
        is_connected = True
        print(f"[{time.time():.2f}] Successfully connected to Myo: {myo_ble_client.address}")

        await discover_myo_uuids(myo_ble_client)

        await set_emg_streaming_mode(myo_ble_client)

        subscription_tasks = []
        for emg_char_uuid in MYO_EMG_CHARACTERISTIC_UUIDS:
            if emg_char_uuid in DYNAMIC_EMG_CHAR_UUIDS:
                subscription_tasks.append(myo_ble_client.start_notify(emg_char_uuid, emg_callback))
                print(f"[{time.time():.2f}] Subscribing to EMG characteristic: {emg_char_uuid}")
            else:
                print(
                    f"[{time.time():.2f}] Warning: Skipped subscription for {emg_char_uuid} as it was not discovered.")

        await asyncio.gather(*subscription_tasks)
        print(f"[{time.time():.2f}] Myo EMG data streaming setup complete.")

        if DYNAMIC_IMU_CHAR_UUIDS:
            try:
                await set_imu_streaming_mode(myo_ble_client)

                for imu_char_uuid in DYNAMIC_IMU_CHAR_UUIDS:
                    await myo_ble_client.start_notify(imu_char_uuid, imu_callback)
                    print(f"[{time.time():.2f}] Subscribing to IMU characteristic: {imu_char_uuid}")

                print(f"[{time.time():.2f}] Myo IMU data streaming setup complete.")
            except Exception as imu_err:
                print(f"[{time.time():.2f}] IMU setup failed (this may be normal): {imu_err}")
        else:
            print(f"[{time.time():.2f}] No IMU characteristics found - continuing without IMU data.")

        asyncio.create_task(monitor_battery_status())

        if frontend_connection_callback:
            frontend_connection_callback(True)

    except Exception as conn_err:
        print(f"[{time.time():.2f}] Failed to connect or set up Myo: {conn_err}")
        is_connected = False
        connected_myo_address_for_frontend = None
        if myo_ble_client:
            await myo_ble_client.disconnect()
            myo_ble_client = None

        if frontend_connection_callback:
            frontend_connection_callback(False)
    finally:
        is_connecting = False

def on_disconnect(client: BleakClient):
    global is_connected, connected_myo_address_for_frontend
    is_connected = False
    connected_myo_address_for_frontend = None

    reset_battery_level()

    print(f"[{time.time():.2f}] Myo disconnected unexpectedly from {client.address}.")
    if frontend_connection_callback:
        frontend_connection_callback(False)

async def start_myo_streamer():
    while not script_should_exit.is_set():
        if backend_command_connect.is_set():
            if not is_connected and not is_connecting:
                try:
                    await connect_to_myo()
                except Exception as e:
                    print(f"[{time.time():.2f}] Error during connection attempt: {e}")
                    await asyncio.sleep(5)
        if backend_command_disconnect.is_set():
            if is_connected:
                if myo_ble_client:
                    await myo_ble_client.disconnect()
                    print(f"[{time.time():.2f}] Disconnected from Myo on user request.")
                backend_command_disconnect.clear()
                backend_command_connect.clear()
        await asyncio.sleep(1)

async def record_csv_for_duration(duration: int, name: str):
    global is_collecting, collected_emg_imu_data, csv_save_success
    collected_emg_imu_data = []
    is_collecting = True
    start_time = time.time()

    with collected_data_lock:
        emg_data_queue.clear()
        imu_data_queue.clear()

    print(f"[{time.time():.2f}] Starting data collection for {duration} seconds...")

    while time.time() - start_time < duration:
        with collected_data_lock:
            while emg_data_queue:
                emg_sample = emg_data_queue.popleft()
                emg_sample['data_type'] = 'emg'
                collected_emg_imu_data.append(emg_sample)

            while imu_data_queue:
                imu_sample = imu_data_queue.popleft()
                imu_sample['data_type'] = 'imu'
                collected_emg_imu_data.append(imu_sample)

        await asyncio.sleep(0.05)

    is_collecting = False
    print(f"[{time.time():.2f}] Data collection finished. Total samples collected: {len(collected_emg_imu_data)}")

    collected_emg_imu_data.sort(key=lambda x: x['timestamp'])

    save_collected_data_to_csv(name, collected_emg_imu_data)
    backend_command_start_recording.clear()
    with recording_param_lock:
        global recording_duration_seconds, recording_name
        recording_duration_seconds = 0
        recording_name = ""

def save_collected_data_to_csv(name: str, data: list):
    global csv_file_path, csv_save_success, csv_folder_path
    csv_save_success = False

    if not csv_folder_path:
        print("[Error] CSV folder not selected. Cannot save data.")
        return

    try:
        if not os.path.exists(csv_folder_path):
            os.makedirs(csv_folder_path, exist_ok=True)

        base_name_to_use = name if name else CSV_BASE_FILENAME
        filepath = get_unique_csv_filename(base_name_to_use, csv_folder_path)
        csv_file_path = filepath

        with open(filepath, 'w', newline='') as file:
            writer = csv.writer(file)
            header = ["Time", "EMG1", "EMG2", "EMG3", "EMG4", "EMG5", "EMG6", "EMG7", "EMG8", "AccX", "AccY", "AccZ", "GyroX", "GyroY", "GyroZ"]
            writer.writerow(header)

            timestamp_groups = {}

            for sample in data:
                ts = sample['timestamp']
                if ts not in timestamp_groups:
                    timestamp_groups[ts] = {
                        'timestamp': ts,
                        'timestamp_readable': sample['timestamp_readable'],
                        'emg': [0] * 8,
                        'imu': [0] * 6,
                        'has_emg': False,
                        'has_imu': False
                    }

                if sample['data_type'] == 'emg':
                    timestamp_groups[ts]['emg'] = sample['emg']
                    timestamp_groups[ts]['has_emg'] = True
                elif sample['data_type'] == 'imu':
                    timestamp_groups[ts]['imu'] = [
                        sample['accel_x'], sample['accel_y'], sample['accel_z'],
                        sample['gyro_x'], sample['gyro_y'], sample['gyro_z']
                    ]
                    timestamp_groups[ts]['has_imu'] = True

            sorted_timestamps = sorted(timestamp_groups.keys())
            last_emg = [0] * 8
            last_imu = [0] * 6

            for ts in sorted_timestamps:
                group = timestamp_groups[ts]

                if group['has_emg']:
                    last_emg = group['emg']
                else:
                    group['emg'] = last_emg

                if group['has_imu']:
                    last_imu = group['imu']
                else:
                    group['imu'] = last_imu

                row = [group['timestamp']] + group['emg'] + group['imu']
                writer.writerow(row)

            csv_save_success = True
            print(f"[{time.time():.2f}] Saved {len(sorted_timestamps)} combined EMG/IMU samples to '{filepath}'")
    except Exception as e:
        print(f"[{time.time():.2f}] [Error] Saving CSV failed: {e}")
        csv_file_path = None
        csv_save_success = False

async def backend_main_loop():
    streamer_task = asyncio.create_task(start_myo_streamer())

    while not script_should_exit.is_set():
        if backend_command_start_recording.is_set():
            with recording_param_lock:
                duration = recording_duration_seconds
                name = recording_name
            await record_csv_for_duration(duration, name)

        if backend_command_vibrate.is_set():
            with vibration_param_lock:
                duration = vibration_duration
            success = await vibrate_myo_backend(duration)
            backend_command_vibrate.clear()

        await asyncio.sleep(0.1)

    streamer_task.cancel()

def run_backend_loop():
    asyncio.run(backend_main_loop())

def get_latest_emg_data():
    with data_lock:
        return np.copy(emg_data)

def get_latest_imu_data():
    with data_lock:
        return np.copy(imu_data)

def is_myo_connected():
    return is_connected

def get_connected_myo_address():
    return connected_myo_address_for_frontend

def set_csv_folder(folder_path):
    global csv_folder_path
    csv_folder_path = folder_path
    print(f"[{time.time():.2f}] CSV save folder set to: {csv_folder_path}")


# Front-End Functionalities

class MyoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EVO EXTRACTOR")
        self.root.geometry("800x450")
        self.root.configure(bg='#001833')
        self.root.resizable(False, False)

        self.center_window()

        self.logo_label = None
        self.logo_image = None
        self.power_button = None
        self.connect_label = None
        self.animation_running = False
        self.is_connected = False

        self.user_name = None
        self.selected_csv_folder = None

        self.latest_emg_data = None
        self.latest_imu_data = None
        self.is_collecting = False
        self.collection_thread = None
        self.data_window = None
        self.countdown_window = None
        self.countdown_label = None
        self.progress_label = None
        self.save_btn = None
        self.cancel_btn = None
        self.duration_entry = None
        self.name_entry = None
        self.timer_label = None

        self.setup_logo()

        global frontend_connection_callback
        frontend_connection_callback = self.backend_connection_state_changed

        self.backend_thread = threading.Thread(target=run_backend_loop, daemon=True)
        self.backend_thread.start()

        set_battery_update_callback(self.update_battery_display)

        self.start_animation()

        self.root.after(1000, self.periodic_ui_update)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def setup_logo(self):
        try:
            logo_path = resource_path("logo.png")
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
            else:
                img = Image.new('RGBA', (250, 250), (70, 130, 180, 255))
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except:
                    font = ImageFont.load_default()

                text = "LOGO"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (250 - text_width) // 2
                y = (250 - text_height) // 2
                draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

            img.thumbnail((250, 250), Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(img)

        except Exception as e:
            print(f"Error loading logo: {e}")
            img = Image.new('RGB', (200, 100), (70, 130, 180))
            self.logo_image = ImageTk.PhotoImage(img)

    def start_animation(self):
        if self.animation_running:
            return

        self.animation_running = True

        self.logo_label = tk.Label(
            self.root,
            image=self.logo_image,
            bg='#001833'
        )
        self.logo_label.place(relx=0.5, rely=0.5, anchor='center')

        threading.Thread(target=self.animate_logo, daemon=True).start()

    def animate_logo(self):
        for alpha in range(0, 101, 5):
            self.root.after(0, lambda a=alpha: self.set_logo_alpha(a))
            time.sleep(0.02)

        time.sleep(2)

        for alpha in range(100, -1, -5):
            self.root.after(0, lambda a=alpha: self.set_logo_alpha(a))
            time.sleep(0.02)

        self.root.after(0, self.show_power_button)

    def set_logo_alpha(self, alpha):
        if self.logo_label:
            if alpha <= 10:
                self.logo_label.configure(state='disabled')
                self.logo_label.place_forget()
            else:
                self.logo_label.configure(state='normal')
                self.logo_label.place(relx=0.5, rely=0.5, anchor='center')

    def show_power_button(self):
        if self.logo_label:
            self.logo_label.destroy()

        button_frame = tk.Frame(self.root, bg='#001833')
        button_frame.place(relx=0.5, rely=0.5, anchor='center')

        self.power_button = tk.Canvas(
            button_frame,
            width=60,
            height=60,
            bg='#001833',
            highlightthickness=0
        )
        self.power_button.pack(pady=(0, 20))

        self.button_bg = self.power_button.create_oval(
            5, 5, 55, 55,
            fill='#2d5aa0',
            outline='',
            tags="button"
        )

        self.power_symbol = self.power_button.create_text(
            30, 30,
            text="⏻",
            font=('Arial', 20, 'bold'),
            fill='white',
            tags="button"
        )

        self.power_button.tag_bind("button", '<Button-1>', lambda event: self.toggle_connection())

        self.connect_label = tk.Label(
            button_frame,
            text="CONNECT ARMBAND",
            font=('Arial', 14, 'bold'),
            fg='white',
            bg='#001833'
        )
        self.connect_label.pack()

        self.add_hover_effects()

        self.animation_running = False

    def add_hover_effects(self):
        def on_enter(event):
            # Check if the mouse is within the circular button
            x, y = event.x, event.y
            if (5 <= x <= 55) and (5 <= y <= 55):
                self.power_button.itemconfig(self.button_bg, fill='#1e3f73')
                self.connect_label.configure(fg='#4dabf7')

        def on_leave(event):
            self.power_button.itemconfig(self.button_bg, fill='#2d5aa0')
            self.connect_label.configure(fg='white')

        def on_press(event):
            x, y = event.x, event.y
            if (5 <= x <= 55) and (5 <= y <= 55):
                self.power_button.itemconfig(self.button_bg, fill='#1a365c')

        def on_release(event):
            x, y = event.x, event.y
            if (5 <= x <= 55) and (5 <= y <= 55):
                self.power_button.itemconfig(self.button_bg, fill='#1e3f73')

        self.power_button.bind('<Enter>', on_enter)
        self.power_button.bind('<Leave>', on_leave)
        self.power_button.bind('<ButtonPress-1>', on_press)
        self.power_button.bind('<ButtonRelease-1>', on_release)

    def toggle_connection(self):
        if not self.is_connected:
            self.connect_label.configure(text="CONNECTING...", fg='#ffd43b')
            self.root.update()

            backend_command_connect.set()
            backend_command_disconnect.clear()

        else:
            backend_command_disconnect.set()
            backend_command_connect.clear()
            messagebox.showinfo("Connection", "Disconnecting Device and Terminating application")
            self.root.destroy()

    def backend_connection_state_changed(self, connected: bool):
        self.root.after(0, lambda: self._update_connection_state(connected))

    def _update_connection_state(self, connected: bool):
        try:
            self.is_connected = connected
            if connected:
                if self.connect_label and self.connect_label.winfo_exists():
                    self.connect_label.configure(text="CONNECTED", fg='#00FF00')
                self.setup_main_ui()
            else:
                if self.connect_label and self.connect_label.winfo_exists():
                    self.connect_label.configure(text="CONNECT ARMBAND", fg='white')
                # If disconnect during main UI, reset UI
                if hasattr(self, "main_ui_frame"):
                    for widget in self.root.winfo_children():
                        widget.destroy()
                    self.show_power_button()
        except tk.TclError as e:
            print(
                f"Widget update error (safe to ignore): {e}")
        except Exception as e:
            print(f"Critical widget update error: {e}")

    def setup_main_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        main_frame = tk.Frame(self.root, bg='#001833', padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_ui_frame = main_frame

        top_frame = tk.Frame(main_frame, bg='#001833')
        top_frame.pack(fill=tk.X, pady=(0, 20))

        status_frame = tk.Frame(top_frame, bg='#001833')
        status_frame.pack(side=tk.RIGHT, padx=(0, 5))

        status_elements_frame = tk.Frame(status_frame, bg='#001833')
        status_elements_frame.pack()

        self.led_label = tk.Label(status_elements_frame, text="●", font=('Arial', 12),
                                  bg='#001833', fg='green')
        self.led_label.pack(side=tk.LEFT, padx=(0, 20))  # Gap after LED

        self.battery_icon_label = tk.Label(status_elements_frame, text="🔋", font=('Arial', 14),
                                           bg='#001833', fg='white')
        self.battery_icon_label.pack(side=tk.LEFT, padx=(0, 3))  # Small gap

        self.battery_percent_label = tk.Label(status_elements_frame, text="N/A", font=('Arial', 10),
                                              bg='#001833', fg='#D3D3D3')
        self.battery_percent_label.pack(side=tk.LEFT)

        self.connect_btn = tk.Button(status_frame, text="connect/disconnect", font=('Arial', 10), width=20, height=2,
                                     bg='#005F89', fg='white', command=self.toggle_connection)
        self.connect_btn.pack(pady=(10, 0))

        profile_frame = tk.Frame(top_frame, relief=tk.RIDGE, bd=2, bg='#001833')
        profile_frame.pack(side=tk.LEFT, fill=tk.X, pady=(0, 10))

        self.profile_label = tk.Label(profile_frame, text='"Active profile name"',
                                      font=('Arial', 10), bg='#001833', fg='white', padx=10, pady=5)
        self.profile_label.pack()

        self.create_profile_btn = tk.Button(profile_frame, text="Create profile",
                                            font=('Arial', 10), width=15,
                                            bg='#005F89', fg='white',
                                            command=self.create_profile)
        self.create_profile_btn.pack()

        center_frame = tk.Frame(main_frame, bg='#001833')
        center_frame.pack(expand=True)

        self.key_mapper_btn = tk.Button(center_frame, text="Key mapper", font=('Arial', 10), width=25, height=2,
                                        bg='#005F89', fg='white', command=self.open_key_mapper)
        self.key_mapper_btn.pack(pady=(0, 10))

        self.data_col_btn = tk.Button(center_frame, text="Data Collection", font=('Arial', 10), width=25, height=2,
                                      bg='#005F89', fg='white', command=self.data_collection)
        self.data_col_btn.pack(pady=(0, 10))

        self.data_viz_btn = tk.Button(center_frame, text="Data Visualize", font=('Arial', 10), width=25, height=2,
                                      bg='#005F89', fg='white', command=self.data_visualize)
        self.data_viz_btn.pack(pady=(0, 10))

        bottom_frame = tk.Frame(main_frame, bg='#001833')
        bottom_frame.pack(fill=tk.X, pady=(20, 0))

        left_bottom_frame = tk.Frame(bottom_frame, bg='#001833')
        left_bottom_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.vibrate_btn = tk.Button(left_bottom_frame, text="Vibrate Armband",
                                     font=('Arial', 10), width=15, height=2,
                                     bg='#005F89', fg='white',
                                     command=self.vibrate_myo)
        self.vibrate_btn.pack()

        right_bottom_frame = tk.Frame(bottom_frame, bg='#001833')
        right_bottom_frame.pack(side=tk.RIGHT, fill=tk.Y)

        about_btn = tk.Button(right_bottom_frame, text="About",
                              font=('Arial', 10), width=15, height=2,
                              bg='#005F89', fg='white',
                              command=self.show_about)
        about_btn.pack()

        try:
            logo_path = resource_path("powered_by.png")
            if os.path.exists(logo_path):
                powered_img = Image.open(resource_path("powered_by.png"))
            else:
                powered_img = Image.new('RGBA', (100, 50), (70, 130, 180, 255))
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(powered_img)
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except:
                    font = ImageFont.load_default()
                text = "Powered By"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (100 - text_width) // 2
                y = (50 - text_height) // 2
                draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

            powered_img.thumbnail((150, 50), Image.Resampling.LANCZOS)
            self.powered_image = ImageTk.PhotoImage(powered_img)
            powered_label = tk.Label(bottom_frame, image=self.powered_image, bg='#001833')
            powered_label.pack(side=tk.BOTTOM, pady=(10, 0))

        except Exception as e:
            print(f"Error loading powered_by.png: {e}")
            powered_img = Image.new('RGB', (100, 50), (70, 130, 180))
            self.powered_image = ImageTk.PhotoImage(powered_img)
            powered_label = tk.Label(bottom_frame, image=self.powered_image, bg='#001833')
            powered_label.pack(side=tk.BOTTOM, pady=(10, 0))

        self.update_connection_status()

    def update_battery_display(self, battery_level):
        self.root.after(0, lambda: self._update_battery_widgets(battery_level))

    def _update_battery_widgets(self, battery_level):
        try:
            if hasattr(self, 'battery_icon_label') and self.battery_icon_label.winfo_exists():
                if battery_level != -1:
                    if battery_level > 75:
                        icon = "🔋"  # Full battery
                    elif battery_level > 50:
                        icon = "🔋"  # Medium battery
                    elif battery_level > 25:
                        icon = "🪫"  # Low battery
                    else:
                        icon = "🪫"  # Very low battery
                    self.battery_icon_label.config(text=icon, fg='white')
                else:
                    self.battery_icon_label.config(text="🪫", fg='#D3D3D3')

            if hasattr(self, 'battery_percent_label') and self.battery_percent_label.winfo_exists():
                if battery_level != -1:
                    self.battery_percent_label.config(text=f"{battery_level}%", fg='white')
                else:
                    self.battery_percent_label.config(text="N/A", fg='#D3D3D3')

        except tk.TclError as e:
            print(f"Battery widget update error: {e}")

    def update_connection_status(self):
        self.is_connected = is_myo_connected()

        try:
            if hasattr(self, 'led_label') and self.led_label.winfo_exists():
                self.led_label.config(text="●", fg="green" if self.is_connected else "red")

            if hasattr(self, 'connect_btn') and self.connect_btn.winfo_exists():
                self.connect_btn.config(text="disconnect" if self.is_connected else "connect")

            state = "normal" if self.is_connected else "disabled"
            fg_color = 'white' if self.is_connected else '#D3D3D3'
            for btn in ['key_mapper_btn', 'create_profile_btn', 'data_col_btn', 'data_viz_btn', 'vibrate_btn']:
                btn_ref = getattr(self, btn, None)
                if btn_ref and btn_ref.winfo_exists():
                    btn_ref.config(state=state, fg=fg_color)

        except tk.TclError as e:
            print(f"[UI] update_connection_status error: {e}")

    def periodic_ui_update(self):
        try:
            self.update_connection_status()
        except Exception as e:
            print(f"[UI] Skipped status update due to error: {e}")
        self.root.after(1000, self.periodic_ui_update)

    def open_key_mapper(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect the device first.")
            return

        mapper_window = tk.Toplevel(self.root)
        mapper_window.title("Key Mapper")
        mapper_window.geometry("750x550")
        mapper_window.configure(bg='#001833')
        mapper_window.resizable(False, False)

        main_frame = tk.Frame(mapper_window, bg='#001833', padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(main_frame, bg='#001833')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        back_btn = tk.Button(header_frame, text="Back",
                             font=('Arial', 10), bg='#005F89', fg='white',
                             command=mapper_window.destroy)
        back_btn.pack(side=tk.RIGHT)

        title_label = tk.Label(main_frame, text="Myo Keyboard Mapper",
                               font=('Arial', 16, 'bold'), bg='#001833', fg='white')
        title_label.pack(pady=(0, 30))

        gestures_frame = tk.Frame(main_frame, bg='#001833')
        gestures_frame.pack(pady=(0, 40))

        gestures = [
            ("Fist", "👊"),
            ("Wave Left", "👈"),
            ("Wave Right", "👉"),
            ("Fingers Spread", "✋"),
            ("Double Tap", "👆")
        ]

        self.gesture_vars = {}
        for i, (gesture_name, gesture_icon) in enumerate(gestures):
            col_frame = tk.Frame(gestures_frame, bg='#001833')
            col_frame.grid(row=0, column=i, padx=20, pady=10)

            name_label = tk.Label(col_frame, text=gesture_name, font=('Arial', 10, 'bold'),
                                  bg='#001833', fg='white')
            name_label.pack()

            icon_frame = tk.Frame(col_frame, bg='#4A4A4A', width=60, height=60,
                                  relief=tk.RAISED, bd=2)
            icon_frame.pack(pady=(5, 10))
            icon_frame.pack_propagate(False)

            icon_label = tk.Label(icon_frame, text=gesture_icon, font=('Arial', 20),
                                  bg='#4A4A4A', fg='white')
            icon_label.pack(expand=True)

            if gesture_name == "Double Tap":
                time_frame = tk.Frame(col_frame, bg='#001833')
                time_frame.pack()

                tk.Label(time_frame, text="Timed Unlock (2s)", font=('Arial', 8),
                         bg='#001833', fg='white').pack()

                var = tk.StringVar(value="Select Key")
                dropdown = ttk.Combobox(time_frame, textvariable=var, width=12,
                                        values=["Select Key", "Space", "Enter", "Ctrl", "Alt",
                                                "Shift", "Tab", "Esc", "F1", "F2", "F3", "F4"])
                dropdown.pack()
                dropdown.state(['readonly'])
            else:
                var = tk.StringVar(value="Select Key")
                dropdown = ttk.Combobox(col_frame, textvariable=var, width=12,
                                        values=["Select Key", "Space", "Enter", "Ctrl", "Alt",
                                                "Shift", "Tab", "Esc", "F1", "F2", "F3", "F4"])
                dropdown.pack()
                dropdown.state(['readonly'])

            self.gesture_vars[gesture_name] = var

        buttons_frame = tk.Frame(main_frame, bg='#001833')
        buttons_frame.pack(side=tk.BOTTOM, pady=(20, 0))

        save_btn = tk.Button(buttons_frame, text="Save", font=('Arial', 12, 'bold'),
                             width=10, height=2, bg='#005F89', fg='white',
                             command=lambda: self.save_mappings(mapper_window))
        save_btn.pack(side=tk.LEFT, padx=(0, 20))

        reset_btn = tk.Button(buttons_frame, text="Reset", font=('Arial', 12, 'bold'),
                              width=10, height=2, bg='#f44336', fg='white',
                              command=self.reset_mappings)
        reset_btn.pack(side=tk.LEFT)

    def save_mappings(self, window):
        mappings = {}
        for gesture, var in self.gesture_vars.items():
            if var.get() != "Select Key":
                mappings[gesture] = var.get()

        if mappings:
            messagebox.showinfo("Mappings Saved",
                                f"Saved mappings:\n" +
                                "\n".join([f"{gesture}: {key}" for gesture, key in mappings.items()]))
        else:
            messagebox.showwarning("No Mappings", "No gesture mappings were selected.")

        window.destroy()

    def reset_mappings(self):
        for var in self.gesture_vars.values():
            var.set("Select Key")
        messagebox.showinfo("Reset", "All mappings have been reset.")

    def create_profile(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect the device first.")
            return

        profile_name = simpledialog.askstring("Create Profile", "Enter profile name:")
        if profile_name:
            self.profile_label.config(text=f'"{profile_name}"', fg='white')
            messagebox.showinfo("Profile Created", f"Profile '{profile_name}' created successfully!")

    def data_visualize(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect the device first.")
            return

        viz_window = tk.Toplevel(self.root)
        viz_window.title("Real-Time Data Visualization")
        viz_window.geometry("1000x800")
        viz_window.configure(bg='#001833')
        viz_window.resizable(True, True)

        main_frame = tk.Frame(viz_window, bg='#001833', relief=tk.SOLID, bd=2)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.fig = Figure(figsize=(12, 14), facecolor='#001833')
        self.fig.subplots_adjust(hspace=0.3)

        self.axes = []
        for i in range(14):
            ax = self.fig.add_subplot(14, 1, i + 1)
            ax.set_facecolor('#001833')
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white')
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')
            self.axes.append(ax)

        self.lines = []
        for i, ax in enumerate(self.axes):
            line, = ax.plot(np.zeros(200), lw=1.5, color='cyan' if i < 8 else 'orange')
            self.lines.append(line)

        labels = [f"EMG {i + 1}" for i in range(8)] + ["Acc X", "Acc Y", "Acc Z", "Gyro X", "Gyro Y", "Gyro Z"]
        colors = ['white'] * 14

        for i, ax in enumerate(self.axes):
            ax.set_ylabel(labels[i], color=colors[i], fontsize=10)

            if i < 8:  # EMG channels
                ax.set_ylim(-128, 128)
            else:  # IMU channels
                if i < 11:  # Accelerometer (channels 8,9,10)
                    ax.set_ylim(-2000, 2000)
                else:  # Gyroscope (channels 11,12,13)
                    ax.set_ylim(-2000, 2000)

            ax.grid(True, alpha=0.3, color='gray')

            if i < 13:
                ax.set_xticks([])
            else:
                ax.set_xlabel('Samples', color='white')

        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        status_frame = tk.Frame(viz_window, bg='#001833')
        status_frame.pack(fill=tk.X, padx=5)

        self.imu_status_label = tk.Label(status_frame, text="IMU Status: Waiting for data...",
                                         bg='#001833', fg='yellow', font=('Arial', 10))
        self.imu_status_label.pack(side=tk.LEFT)

        self.data_counter_label = tk.Label(status_frame, text="Packets: EMG=0, IMU=0",
                                           bg='#001833', fg='white', font=('Arial', 10))
        self.data_counter_label.pack(side=tk.RIGHT)

        self.emg_packet_count = 0
        self.imu_packet_count = 0
        self.last_imu_update = time.time()

        self.update_plot(viz_window)

    def update_plot(self, viz_window):
        try:
            current_time = time.time()
            self.latest_emg_data = get_latest_emg_data()
            self.latest_imu_data = get_latest_imu_data()

            emg_updated = False
            for i in range(8):
                if np.any(self.latest_emg_data[i] != 0):
                    self.lines[i].set_ydata(self.latest_emg_data[i])
                    emg_updated = True

            if emg_updated:
                self.emg_packet_count += 1

            imu_updated = False
            for i in range(6):
                if np.any(self.latest_imu_data[i] != 0) or (current_time - self.last_imu_update < 0.1 and self.imu_packet_count > 0):
                    self.lines[8 + i].set_ydata(self.latest_imu_data[i])
                    imu_updated = True

            if imu_updated:
                self.imu_packet_count += 1
                self.last_imu_update = current_time

            if hasattr(self, 'imu_status_label'):
                time_since_imu = current_time - self.last_imu_update
                if time_since_imu < 2.0:
                    status_text = "IMU Status: Receiving data"
                    status_color = 'green'
                else:
                    status_text = f"IMU Status: No data for {time_since_imu:.1f}s"
                    status_color = 'red'

                self.imu_status_label.config(text=status_text, fg=status_color)

            if hasattr(self, 'data_counter_label'):
                self.data_counter_label.config(
                    text=f"Packets: EMG={self.emg_packet_count}, IMU={self.imu_packet_count}")

            self.canvas.draw_idle()

            if viz_window.winfo_exists():
                viz_window.after(50, lambda: self.update_plot(viz_window))

        except tk.TclError:
            pass
        except Exception as e:
            print(f"Plot update error: {e}")
            if viz_window.winfo_exists():
                viz_window.after(100, lambda: self.update_plot(viz_window))


    def data_collection(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect the device first.")
            return

        self.data_window = tk.Toplevel(self.root)
        self.data_window.title("Data Collection Setup")
        self.data_window.geometry("500x350")
        self.data_window.configure(bg='#001833')
        self.data_window.resizable(False, False)
        self.data_window.transient(self.root)
        self.data_window.grab_set()

        main_frame = tk.Frame(self.data_window, bg='#001833', padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)

        # Username input
        name_frame = tk.Frame(main_frame, bg='#001833')
        name_frame.pack(fill='x', pady=(0, 15))
        tk.Label(name_frame, text="Enter Your Name:", font=('Arial', 12), bg='#001833', fg='white').pack(anchor='w')
        self.name_entry = tk.Entry(name_frame, font=('Arial', 10), width=35, bg='#4A4A4A', fg='white', insertbackground='white')
        self.name_entry.pack(fill='x', pady=(5,0))

        folder_frame = tk.Frame(main_frame, bg='#001833')
        folder_frame.pack(fill='x', pady=(15, 15))
        tk.Label(folder_frame, text="Choose CSV Save Folder:", font=('Arial', 12), bg='#001833', fg='white').pack(anchor='w')
        folder_select_btn = tk.Button(folder_frame, text="Select Folder", font=('Arial', 10),
                                      bg='#005F89', fg='white', command=self.choose_csv_folder)
        folder_select_btn.pack(side='left', padx=(0, 10))
        self.folder_path_label = tk.Label(folder_frame, text="No folder selected", font=('Arial', 9),
                                         bg='#001833', fg='gray')
        self.folder_path_label.pack(side='left', fill='x', expand=True)

        duration_frame = tk.Frame(main_frame, bg='#001833')
        duration_frame.pack(fill='x', pady=(15, 15))
        tk.Label(duration_frame, text="Data collection time duration (seconds):",
                 font=('Arial', 12), bg='#001833', fg='white').pack(anchor='w')
        self.duration_entry = tk.Entry(duration_frame, font=('Arial', 10), width=35, bg='#4A4A4A', fg='white', insertbackground='white')
        self.duration_entry.pack(fill='x', pady=(5,0))

        buttons_frame = tk.Frame(main_frame, bg='#001833')
        buttons_frame.pack(fill='x', pady=(20, 0))

        submit_btn = tk.Button(buttons_frame, text="Start Collection", font=('Arial', 12, 'bold'),
                               bg='#005F89', fg='white',
                               command=self.validate_and_start_collection)
        submit_btn.pack(side='left', padx=(0,10), expand=True)

        cancel_btn = tk.Button(buttons_frame, text="Cancel", font=('Arial', 12),
                               bg='#f44336', fg='white',
                               command=self.data_window.destroy)
        cancel_btn.pack(side='right', expand=True)

    def choose_csv_folder(self):
        folder_path = filedialog.askdirectory(parent=self.data_window, title="Select Folder to Save CSV")
        if folder_path:
            self.selected_csv_folder = folder_path
            self.folder_path_label.config(text=os.path.basename(folder_path), fg='white')
            set_csv_folder(folder_path)
            messagebox.showinfo("Folder Selected", f"CSV files will be saved in:\n{folder_path}")
        else:
            self.selected_csv_folder = None
            self.folder_path_label.config(text="No folder selected", fg='gray')
            messagebox.showwarning("No Folder Selected", "Please select a folder to save your data.")
            set_csv_folder(None)

    def validate_and_start_collection(self):
        username = self.name_entry.get().strip()
        duration_str = self.duration_entry.get().strip()

        if not username:
            messagebox.showwarning("Input Error", "Please enter a username.")
            return
        if not self.selected_csv_folder:
            messagebox.showwarning("Input Error", "Please select a CSV save folder.")
            return

        try:
            duration = int(duration_str)
            if duration <= 0:
                raise ValueError("Duration must be a positive number.")
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter a valid positive number for duration.")
            return

        self.user_name = username
        self.data_window.destroy()  # Close the setup window

        self.start_countdown_and_collection(duration, username)


    def start_countdown_and_collection(self, duration, username):
        self.countdown_window = tk.Toplevel(self.root)
        self.countdown_window.title("Data Collection in Progress")
        self.countdown_window.geometry("350x200")
        self.countdown_window.configure(bg='#001833')
        self.countdown_window.resizable(False, False)
        self.countdown_window.transient(self.root)
        self.countdown_window.grab_set()

        countdown_frame = tk.Frame(self.countdown_window, bg='#001833', padx=20, pady=20)
        countdown_frame.pack(fill='both', expand=True)

        self.timer_label = tk.Label(countdown_frame, text="Starting...", font=('Arial', 24, 'bold'), bg='#001833', fg='white')
        self.timer_label.pack(pady=(0, 10))

        self.progress_label = tk.Label(countdown_frame, text="Preparing to collect data...", font=('Arial', 12), bg='#001833', fg='white')
        self.progress_label.pack()

        self.toggle_main_ui_buttons(False)

        self.remaining_time = duration
        self.update_countdown_label()

        self.countdown_window.after(1000, lambda: self._initiate_backend_recording(duration, username))

    def _initiate_backend_recording(self, duration, username):
        global recording_duration_seconds, recording_name
        with recording_param_lock:
            recording_duration_seconds = duration
            recording_name = username
        backend_command_start_recording.set()
        self.is_collecting = True

        self.root.after(100, self.check_recording_completion)


    def update_countdown_label(self):
        if self.countdown_window and self.countdown_window.winfo_exists():
            if self.remaining_time > 0:
                self.timer_label.config(text=f"{self.remaining_time} seconds remaining")
                self.progress_label.config(text="Collecting data...")
                self.remaining_time -= 1
                self.countdown_window.after(1000, self.update_countdown_label)
            elif self.is_collecting:
                self.timer_label.config(text="Processing data...")
                self.progress_label.config(text="Please wait...")
                self.countdown_window.after(500, self.update_countdown_label)
        else:
            self.is_collecting = False


    def check_recording_completion(self):
        if self.is_collecting and backend_command_start_recording.is_set():
            if self.countdown_window and self.countdown_window.winfo_exists():
                self.root.after(500, self.check_recording_completion)
        else:
            self.is_collecting = False
            self.show_save_result()
            self.toggle_main_ui_buttons(True)

    def show_save_result(self):
        if self.countdown_window and self.countdown_window.winfo_exists():
            self.countdown_window.destroy()

        if csv_save_success:
            messagebox.showinfo("Data Collection Complete",
                                f"Data collected and saved successfully!\nFile: {csv_file_path}")
        else:
            messagebox.showerror("Data Collection Failed",
                                 "Failed to save data. Check console for errors.")

    def toggle_main_ui_buttons(self, enable: bool):
        state = "normal" if enable else "disabled"
        fg_color = 'white' if enable else '#D3D3D3'
        for btn_name in ['key_mapper_btn', 'create_profile_btn', 'data_col_btn', 'data_viz_btn', 'vibrate_btn', 'connect_btn']:
            btn_ref = getattr(self, btn_name, None)
            if btn_ref and btn_ref.winfo_exists():
                btn_ref.config(state=state, fg=fg_color if enable else '#D3D3D3')

    def open_concern_form(self):
        messagebox.showinfo("Concern Form", "Opening concern form...")

    def vibrate_myo(self):
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect the device first.")
            return

        global vibration_duration
        with vibration_param_lock:
            vibration_duration = 3  # Default to Long vibration
            backend_command_vibrate.set()

        messagebox.showinfo("Vibrate", "Myo vibration triggered!")

    def show_about(self):
        about_message = """EVO EXTRACTOR
Version 1.0
Developed by R & D Team, EVOMED Technology.

This application interfaces with the Myo Armband to collect EMG and IMU data, and save it to CSV files, and visualize it in real-time. It also includes features such as Vibrate Myo, dynamic Battery Icon, Battery Level, and Connection Status.

Thank you for using EVO EXTRACTOR!
"""
        messagebox.showinfo("About EVO EXTRACTOR", about_message)


# Main application entry point

if __name__ == "__main__":
    app = MyoApp()
    app.root.mainloop()