import network
import socket
import time
import BME280
from machine import Pin, I2C
from capsense import CapsenseReader
import os
import uasyncio as asyncio

AP_NAME = "PicoLogger_0"
AP_PW = "capsense123"

logging_status = {
    'active': False,
    'label': '',
    'start_time': 0,
    'duration': 0,
    'type': ''  # 'single' or 'batch'
}

led = Pin("LED", Pin.OUT)
led.off()
# Set VCC on pin 28 to power capsense board
VCC_PIN_1 = Pin(28, Pin.OUT)
VCC_PIN_1.on()
print("VCC pins 28 set high for power supply")

# Initialize hardware with basic error handling
try:
    i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=10000)    # I2C0 for BME280
    i2c1 = I2C(1, scl=Pin(3), sda=Pin(2), freq=40000)   # I2C1 for capsense
    capsense_reader = CapsenseReader(i2c_instance=i2c1)
    print("Using shared I2C instance")
    print("Capsense sensor found at 0x09")
except Exception as e:
    print(f"Sensor init error: {e}")
    capsense_reader = None



# Create logs directory
try:
    os.mkdir('logs')
except:
    print("Logs directory already exists or cannot be created")

# HTML content (keep your existing HTML)
html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PicoLogger</title>
<style>
body{font-family:Arial,sans-serif;margin:10px;background:#f0f0f0}
.container{max-width:320px;margin:0 auto;background:white;padding:15px;border-radius:5px}
h1{text-align:center;margin:0 0 15px 0;font-size:18px;color:#333}
.group{margin-bottom:12px}
label{display:block;margin-bottom:3px;font-weight:bold;font-size:13px;color:#555}
input{width:100%;padding:6px;border:1px solid #ccc;border-radius:3px;box-sizing:border-box;font-size:14px}
input:focus{border-color:#4CAF50;outline:none}
.time{display:flex;gap:5px;align-items:center}
.time-part{flex:1}
.sep{font-weight:bold;font-size:16px}
button{width:100%;padding:10px;background:#4CAF50;color:white;border:none;border-radius:3px;font-size:15px;margin-top:8px}
button:disabled{background:#ccc}
.batch-btn{background:#2196F3;margin-top:5px}
.batch-btn:disabled{background:#ccc}
.status{margin-top:10px;padding:8px;border-radius:3px;text-align:center;display:none;font-size:13px}
.success{background:#d4edda;color:#155724}
.error{background:#f8d7da;color:#721c24}
.info{background:#d1ecf1;color:#0c5460}
.button-group{display:flex;gap:5px}
.button-group button{flex:1;margin-top:8px}
</style>
</head>
<body>
<div class="container">
<h1>PicoLogger</h1>
<form id="form">
<div class="group">
<label>Duration (sec)</label>
<input type="number" id="duration" min="1" max="100000" value="60" required>
</div>
<div class="group">
<label>Sample Rate (Hz)</label>
<input type="number" id="rate" min="0.01" max="10" step="0.01" value="0.1" required>
</div>
<div class="group">
<label>Time (24h)</label>
<div class="time">
<div class="time-part">
<input type="number" id="h" min="0" max="23" value="12" required>
</div>
<div class="sep">:</div>
<div class="time-part">
<input type="number" id="m" min="0" max="59" value="0" required>
</div>
</div>
</div>
<div class="group">
<label>Date</label>
<input type="date" id="date" required>
</div>
<div class="group">
<label>Label</label>
<input type="text" id="label" maxlength="20" required>
</div>
<div class="button-group">
<button type="submit" id="btn">Start Single Log</button>
<button type="button" id="batch-btn" class="batch-btn">Start Batch (4x)</button>
</div>
</form>
<div id="status" class="status"></div>
</div>
<script>
function setTime(){
var d=new Date();
document.getElementById('h').value=d.getHours();
document.getElementById('m').value=d.getMinutes();
var year = d.getFullYear();
var month = String(d.getMonth() + 1).padStart(2, '0');
var day = String(d.getDate()).padStart(2, '0');
document.getElementById('date').value = year + '-' + month + '-' + day;
}
setTime();

function disableButtons(disabled) {
    document.getElementById('btn').disabled = disabled;
    document.getElementById('batch-btn').disabled = disabled;
}

function showStatus(message, type) {
    var status = document.getElementById('status');
    status.className = 'status ' + type;
    status.textContent = message;
    status.style.display = 'block';
}

function hideStatus() {
    document.getElementById('status').style.display = 'none';
}

function startLogging(endpoint, buttonText, successMessage) {
    var h = document.getElementById('h').value;
    var m = document.getElementById('m').value;
    var date = document.getElementById('date').value;
    if (h < 10) h = '0' + h;
    if (m < 10) m = '0' + m;

    disableButtons(true);
    document.getElementById('btn').textContent = buttonText;
    document.getElementById('batch-btn').textContent = buttonText;
    hideStatus();

    var params = "duration=" + encodeURIComponent(document.getElementById('duration').value) +
                 "&sample_rate=" + encodeURIComponent(document.getElementById('rate').value) +
                 "&date=" + encodeURIComponent(date) +
                 "&clock_time=" + encodeURIComponent(h + ":" + m) +
                 "&label=" + encodeURIComponent(document.getElementById('label').value);

    var xhr = new XMLHttpRequest();
    xhr.open('POST', endpoint, true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function() {
        if (xhr.status === 200) {
            showStatus(successMessage, 'success');
            document.getElementById('label').value = '';
        } else {
            showStatus('Failed', 'error');
        }
        disableButtons(false);
        document.getElementById('btn').textContent = 'Start Single Log';
        document.getElementById('batch-btn').textContent = 'Start Batch (4x)';
        setTimeout(hideStatus, 5000);
    };
    xhr.onerror = function() {
        showStatus('Connection Error', 'error');
        disableButtons(false);
        document.getElementById('btn').textContent = 'Start Single Log';
        document.getElementById('batch-btn').textContent = 'Start Batch (4x)';
        setTimeout(hideStatus, 5000);
    };
    xhr.send(params);
}

// Single logging
document.getElementById('form').onsubmit = function(e) {
    e.preventDefault();
    startLogging('/start_logging', 'Logging...', 'Single log finished!');
};

// Batch logging
document.getElementById('batch-btn').onclick = function(e) {
    e.preventDefault();
    if (document.getElementById('form').checkValidity()) {
        startLogging('/start_batch', 'Batch logging...', 'Batch complete! (4 files created)');
    } else {
        showStatus('Please fill all fields', 'error');
        setTimeout(hideStatus, 3000);
    }
};
</script>
</body>
</html>
"""

# Configure the Pico W as an access point
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=AP_NAME, password=AP_PW) 
print("Access point created. SSID:", AP_NAME, ", Password:", AP_PW)

while not ap.active():
    time.sleep(1)

print("Access point is active. IP:", ap.ifconfig()[0])

# Start HTTP server
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(1)
print("Listening on", addr)

def getBMEdata():
    """Get BME280 data with simple error handling"""
    try:
        bme = BME280.BME280(i2c=i2c)
        return bme.temperature, bme.humidity, bme.pressure
    except Exception as e:
        print(f"BME280 error: {e}")
        return "ERROR", "ERROR", "ERROR"

def get_capsense_data():
    """Get capsense data with error handling"""
    if capsense_reader is None:
        return "NO_SENSOR," * 11 + "NO_SENSOR"  # 12 values
    
    try:
        capsense_csv = capsense_reader.get_csv_string()
        if capsense_csv:
            return capsense_csv
        else:
            return "EMPTY," * 11 + "EMPTY"
    except Exception as e:
        print(f"Capsense error: {e}")
        return "ERROR," * 11 + "ERROR"

async def record_batch_data(duration, sample_rate, label, clock_time, start_date):
    """Record 4 batches of data asynchronously."""
    global logging_status

    logging_status['active'] = True
    logging_status['label'] = label
    logging_status['start_time'] = time.time()
    logging_status['duration'] = duration * 4 + 6  # 4 logs + gaps
    logging_status['type'] = 'batch'

    print(f"Starting batch recording: {label}")
    print(f"Will create 4 files: {label}_1.csv to {label}_4.csv")

    for i in range(1, 5):
        batch_label = f"{label}_{i}"
        print(f"\n=== Batch {i}/4: {batch_label} ===")

        batch_start_seconds = 0
        if i > 1:
            batch_start_seconds = (i - 1) * (duration + 2)

        hours, minutes = map(int, clock_time.split(':'))
        start_seconds = hours * 3600 + minutes * 60

        new_hours = int((start_seconds // 3600) % 24)
        new_minutes = int((start_seconds % 3600) // 60)
        batch_clock_time = f"{new_hours:02d}:{new_minutes:02d}"

        print(f"Batch {i} start time: {batch_clock_time}")

        await execute_logging(duration, sample_rate, batch_label, batch_clock_time, start_date)

        if i < 4:
            print(f"Waiting 2 seconds before batch {i+1}...")
            await asyncio.sleep(2)

    logging_status['active'] = False
    logging_status['label'] = ''
    print("Batch recording finished.")


def read_http_request(cl):
    """Read and parse HTTP request"""
    try:
        cl.settimeout(5.0)  # Increased timeout
        request = cl.recv(4096).decode('utf-8')
        print(f"Raw request received: {len(request)} bytes")
        
        if '\r\n\r\n' in request:
            headers, body = request.split('\r\n\r\n', 1)
        else:
            headers = request
            body = ""
        
        # For POST requests, check if we need to read more data
        if "POST" in headers and "Content-Length:" in headers:
            try:
                # Extract content length from headers
                lines = headers.split('\r\n')
                content_length = 0
                for line in lines:
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':')[1].strip())
                        break
                
                print(f"Content-Length: {content_length}, Body length: {len(body)}")
                
                # If we haven't received all the body data, read more
                while len(body) < content_length:
                    remaining = content_length - len(body)
                    additional_data = cl.recv(min(remaining, 1024)).decode('utf-8')
                    if not additional_data:
                        break
                    body += additional_data
                    print(f"Read additional {len(additional_data)} bytes, total body: {len(body)}")
                    
            except Exception as e:
                print(f"Error reading POST body: {e}")
        
        return headers, body
    except Exception as e:
        print(f"Request read error: {e}")
        return "", ""

def parse_form_data(body):
    """Parse URL-encoded form data"""
    data = {}
    if body:
        pairs = body.split('&')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                # Simple URL decode for common characters
                value = value.replace('%20', ' ').replace('%3A', ':').replace('%2D', '-')
                data[key] = value
    print(f"Form data parsed: {data}")  # Debugging print
    return data

async def execute_logging(duration, sample_rate, label, clock_time, start_date):
    """Execute single logging session asynchronously."""
    global logging_status

    # Set logging status to active
    logging_status['active'] = True
    logging_status['label'] = label
    logging_status['start_time'] = time.time()
    logging_status['duration'] = duration
    logging_status['type'] = 'single'

    print(f"Starting logging: {label}")
    print(f"Duration: {duration}s, Rate: {sample_rate}Hz")
    print(f"Start date: {start_date}, Clock time: {clock_time}")

    led.on()

    try:
        # Parse the start date and time
        year, month, day = map(int, start_date.split('-'))
        hours, minutes = map(int, clock_time.split(':'))
        start_seconds = hours * 3600 + minutes * 60

        interval = 1.0 / sample_rate
        total_samples = int(duration * sample_rate)

        print(f"Sample interval: {interval:.2f} seconds")
        print(f"Total samples: {total_samples}")

        # Create CSV header
        if capsense_reader:
            capsense_header = capsense_reader.get_csv_header()
        else:
            capsense_header = "capsense_unavailable"

        csv_header = f"Time,BME280_temperature,BME280_humidity,BME280_pressure,{capsense_header}\n"

        # Write header to file with error handling
        try:
            with open(f"logs/{label}.csv", "w") as f:
                f.write(csv_header)
            print(f"Created CSV file: logs/{label}.csv")
        except Exception as e:
            print(f"Error creating file: {e}")
            logging_status['active'] = False
            return

        successful_samples = 0
        failed_samples = 0
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 5;

        # Open file once and keep it open for better performance
        try:
            log_file = open(f"logs/{label}.csv", "a")
        except Exception as e:
            print(f"Error opening file: {e}")
            logging_status['active'] = False
            return

        for i in range(total_samples):
            try:
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"Stopping: {MAX_CONSECUTIVE_ERRORS} consecutive errors")
                    break

                # Only print every 10th sample to reduce overhead
                if i % 10 == 0 or i < 3:
                    print(f"Logging sample {i+1}/{total_samples}...")

                # Get sensor data
                temperature, humidity, pressure = getBMEdata()
                capsense_csv = get_capsense_data()

                # Calculate current datetime based on start parameters and sample number
                current_total_seconds = start_seconds + (i * interval)
                current_day_offset = int(current_total_seconds // 86400)
                current_seconds_in_day = current_total_seconds % 86400

                current_hours = int(current_seconds_in_day // 3600)
                current_minutes = int((current_seconds_in_day % 3600) // 60)
                current_seconds = int(current_seconds_in_day % 60)
                current_milliseconds = int((current_seconds_in_day % 1) * 1000)

                if current_day_offset == 0:
                    current_date = f"{year:04d}-{month:02d}-{day:02d}"
                else:
                    # Handle day rollover (simplified)
                    new_day = day + current_day_offset
                    new_month = month
                    new_year = year
                    
                    while new_day > 30:  # Simplified - you might want more accurate month handling
                        new_day -= 30
                        new_month += 1
                        if new_month > 12:
                            new_month = 1
                            new_year += 1
                    
                    current_date = f"{new_year:04d}-{new_month:02d}-{new_day:02d}"

                datetime_str = f"{current_date} {current_hours:02d}:{current_minutes:02d}:{current_seconds:02d}.{current_milliseconds:03d}"

                log_entry = f"{datetime_str},{temperature},{humidity},{pressure},{capsense_csv}\n"

                try:
                    log_file.write(log_entry)
                    log_file.flush();
                    successful_samples += 1
                    consecutive_errors = 0
                except Exception as e:
                    print(f"File write error at sample {i+1}: {e}")
                    failed_samples += 1
                    consecutive_errors += 1

            except Exception as e:
                print(f"Sample {i+1} error: {e}")
                failed_samples += 1
                consecutive_errors += 1

            # Wait for the next sample (remove the verbose print)
            await asyncio.sleep(interval)

        # Close the file
        log_file.close()

        print(f"Logging complete: {successful_samples}/{total_samples} samples logged successfully.")
        logging_status['active'] = False
        logging_status['label'] = ''

    except Exception as e:
        print(f"Critical logging error: {e}")
        logging_status['active'] = False
    finally:
        led.off()

async def http_server():
    """Handle HTTP requests asynchronously."""
    s.setblocking(False)
    
    while True:
        try:
            await asyncio.sleep(0.01)
            
            try:
                cl, addr = s.accept()
                print("Client connected from", addr)
                
                try:
                    headers, body = read_http_request(cl)

                    # Serve the main page
                    if "GET / " in headers or "GET / HTTP/1.1" in headers:
                        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + html
                        cl.send(response.encode())
                        print("Main page served.")

                    # Handle single logging request
                    elif "POST" in headers and "/start_logging" in headers:
                        print("Received /start_logging request")
                        data = parse_form_data(body)

                        duration = int(data.get('duration', '60'))
                        sample_rate = float(data.get('sample_rate', '0.1'))
                        label = data.get('label', 'default')
                        clock_time = data.get('clock_time', '12:00')
                        start_date = data.get('date', '2024-01-01')

                        print(f"Starting logging with duration={duration}, sample_rate={sample_rate}, label={label}")

                        # Create and start the logging task
                        task = asyncio.create_task(execute_logging(duration, sample_rate, label, clock_time, start_date))
                        print(f"Logging task created: {task}")

                        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK"
                        cl.send(response.encode())

                    # Handle batch logging request
                    elif "POST" in headers and "/start_batch" in headers:
                        print("Received /start_batch request")
                        data = parse_form_data(body)

                        duration = int(data.get('duration', '60'))
                        sample_rate = float(data.get('sample_rate', '0.1'))
                        label = data.get('label', 'batch')
                        clock_time = data.get('clock_time', '12:00')
                        start_date = data.get('date', '2024-01-01')

                        print(f"Starting batch logging with duration={duration}, sample_rate={sample_rate}, label={label}")

                        # Create and start the batch logging task
                        task = asyncio.create_task(record_batch_data(duration, sample_rate, label, clock_time, start_date))
                        print(f"Batch logging task created: {task}")

                        response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK"
                        cl.send(response.encode())

                    # Handle status request
                    elif "GET /status" in headers:
                        if logging_status['active']:
                            elapsed = int(time.time() - logging_status['start_time'])
                            remaining = max(0, logging_status['duration'] - elapsed)
                            status_text = f"ACTIVE: {logging_status['type']} '{logging_status['label']}' - {elapsed}s elapsed, {remaining}s remaining"
                        else:
                            status_text = "IDLE"

                        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n{status_text}"
                        cl.send(response.encode())
                        print(f"Status request served: {status_text}")

                    # Handle unknown requests
                    else:
                        response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nNot Found"
                        cl.send(response.encode())
                        print("Unknown request received.")

                except Exception as e:
                    print(f"Error handling request: {e}")

                finally:
                    cl.close()
                    
            except OSError:
                # No connection available - this is normal for non-blocking socket
                continue
                
        except Exception as e:
            print(f"Error in server loop: {e}")
            await asyncio.sleep(0.1)

async def main():
    await asyncio.gather(http_server())

asyncio.run(main())