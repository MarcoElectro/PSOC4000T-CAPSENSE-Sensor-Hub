"""
CapSense Sensor Reader for Raspberry Pi Pico 2W

This module provides an interface for reading data from Infineon's PSOC CAPSENSE sensors
over I2C. It's designed to work with PSOC 4000T CAPSENSE controllers and similar devices.

Features:
- Flexible I2C communication with configurable pins and frequency
- Support for multiple CAPSENSE sensors on a single I2C bus
- Automatic sensor detection and connection retries
- Customizable sensor configuration
- Data output in various formats (raw, structured dict, CSV)

Hardware connections:
- Connect GND to GND
- Connect 3.3V to VCC (if needed)
- Connect SDA to GPIO2 (default)
- Connect SCL to GPIO3 (default)

Requirements:
- Raspberry Pi Pico with MicroPython
- Infineon PSOC CAPSENSE microcontroller with sensor data in an EzI2C buffer
"""


import struct
import time
from machine import Pin, I2C

# Default configuration - easily modifiable
DEFAULT_CONFIG = {
    'sensor_address': 0x09,
    'register': 0x00,
    'num_sensors': 3,
    'values_per_sensor': 3,  # rawcount, diffcount, baseline
    'value_size': 2,  # 2 bytes per value (uint16)
    'sensor_names': ['CSD_360', 'CSD_100', 'CSD_20'],
    'value_names': ['RawCount', 'DiffCount', 'Baseline']
}

class CapsenseReader:
    """Flexible capsense sensor reader"""
    
    def __init__(self, scl_pin=3, sda_pin=2, freq=40000, config=None, i2c_instance=None):
        """
        Initialize capsense reader
        
        Args:
            scl_pin (int): SCL pin number (ignored if i2c_instance provided)
            sda_pin (int): SDA pin number (ignored if i2c_instance provided)
            freq (int): I2C frequency (ignored if i2c_instance provided)
            config (dict): Sensor configuration (optional)
            i2c_instance: Existing I2C instance to reuse
        """
        # Use provided config or default
        self.config = config if config else DEFAULT_CONFIG.copy()
        
        # Calculate buffer size
        self.buffer_size = (self.config['num_sensors'] * 
                           self.config['values_per_sensor'] * 
                           self.config['value_size'])
        
        # Use existing I2C instance or create new one
        if i2c_instance:
            self.i2c = i2c_instance
            print("Using shared I2C instance")
        else:
            self.i2c = I2C(1, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
            print("Created new I2C instance")
            
        self.is_available = False
        
        # Check sensor availability
        self._check_sensor_availability()
    
    def _check_sensor_availability(self, max_attempts=3, delay=0.5):
        """Check if sensor is available, retry a few times"""
        attempts = 0
        while attempts < max_attempts and not self.is_available:
            try:
                devices = self.i2c.scan()
                addr = self.config['sensor_address']
                if addr in devices:
                    self.is_available = True
                    print(f"Capsense sensor found at 0x{addr:02X}")
                else:
                    print(f"Warning: Sensor not found at 0x{addr:02X}")
                    print(f"Available: {[hex(d) for d in devices]}")
                    attempts += 1
                    time.sleep(delay)
            except Exception as e:
                print(f"I2C error: {e}")
                attempts += 1
                time.sleep(delay)
        if not self.is_available:
            print("Capsense sensor not available after retries.")
    
    def read_raw_data(self):
        """Read raw bytes from sensor"""
        if not self.is_available:
            raise Exception("Sensor not available")
        
        try:
            data = self.i2c.readfrom_mem(
                self.config['sensor_address'], 
                self.config['register'], 
                self.buffer_size
            )
            
            if len(data) != self.buffer_size:
                raise ValueError(f"Expected {self.buffer_size} bytes, got {len(data)}")
            
            return data
        except Exception as e:
            raise Exception(f"Read failed: {e}")
    
    def read_sensor_data(self):
        """
        Read and parse sensor data
        
        Returns:
            dict: Organized sensor data
        """
        raw_data = self.read_raw_data()
        
        # Unpack all values as uint16 little-endian
        total_values = self.config['num_sensors'] * self.config['values_per_sensor']
        values = struct.unpack(f'<{total_values}H', raw_data)
        
        # Debug: print all unpacked values
        print(",".join(str(v) for v in values))
        
        # C struct layout:
        # struct {
        #     uint16_t rawcount[NUM_OF_SENSORS];  // First all raw counts
        #     uint16_t diffcount[NUM_OF_SENSORS]; // Then all diff counts 
        #     uint16_t baseline[NUM_OF_SENSORS];  // Then all baselines
        # } capsense_data;
        
        sensor_data = {}
        num_sensors = self.config['num_sensors']
        value_names = self.config['value_names']
        
        # Create a mapping between array index and sensor name
        # Based on the observed output pattern
        index_to_sensor = {
            0: 'CSD_360',  # First raw value
            1: 'CSD_100',  # Second raw value
            2: 'CSD_20'    # Third raw value
        }
        
        # Initialize all sensor data dictionaries
        for sensor_name in self.config['sensor_names'][:num_sensors]:
            sensor_data[sensor_name] = {}
        
        # For each sensor position in the raw data
        for i in range(num_sensors):
            # Get the sensor name corresponding to this position
            sensor_name = index_to_sensor[i]
            
            # For each value type (RawCount, DiffCount, Baseline)
            for j, value_name in enumerate(value_names):
                # Calculate index in the unpacked values array
                value_index = (j * num_sensors) + i
                sensor_data[sensor_name][value_name] = values[value_index]
        
        return sensor_data
    
    def get_raw_data(self):
        """
        Get only the raw count values from all sensors.
        
        Returns:
            dict: Dictionary with sensor names as keys and raw count values as values
        """
        try:
            data = self.read_sensor_data()
            raw_values = {}
            
            for sensor_name in self.config['sensor_names'][:self.config['num_sensors']]:
                raw_values[sensor_name] = data[sensor_name]['RawCount']
            
            return raw_values
        except Exception as e:
            print(f"Error getting raw data: {e}")
            return None
    
    def get_csv_header(self):
        """Generate CSV header based on configuration"""
        headers = []
        num_sensors = self.config['num_sensors']
        values_per_sensor = self.config['values_per_sensor']
        
        for sensor_name in self.config['sensor_names'][:num_sensors]:
            for value_name in self.config['value_names'][:values_per_sensor]:
                headers.append(f"{sensor_name}_{value_name}")
        
        return ','.join(headers)
    
    def get_csv_string(self):
        """Get sensor data as CSV string"""
        try:
            data = self.read_sensor_data()
            values = []
            
            num_sensors = self.config['num_sensors']
            values_per_sensor = self.config['values_per_sensor']
            
            for sensor_name in self.config['sensor_names'][:num_sensors]:
                for value_name in self.config['value_names'][:values_per_sensor]:
                    values.append(str(data[sensor_name][value_name]))
            
            return ','.join(values)
        except Exception as e:
            print(f"CSV error: {e}")
            return None
    
    def test_sensor(self, num_samples=100):
        """Test sensor reading with specified number of samples"""
        print(f"Testing capsense sensor ({num_samples} samples)...")
        
        if not self.is_available:
            print("Sensor not available")
            return
        
        for i in range(num_samples):
            try:
                data = self.read_sensor_data()
                print(f"Sample {i+1}:")
                
                # Iterate in config order to maintain consistent ordering
                for sensor_name in self.config['sensor_names']:
                    if sensor_name in data:
                        sensor_values = data[sensor_name]
                        value_str = ", ".join([f"{name}={value}" for name, value in sensor_values.items()])
                        print(f"  {sensor_name}: {value_str}")
                
                if i < num_samples - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error reading sample {i+1}: {e}")
# Convenience functions
def create_capsense_reader(scl_pin=3, sda_pin=2, freq=40000, config=None, i2c_instance=None):
    """Create capsense reader with optional custom configuration"""
    return CapsenseReader(scl_pin, sda_pin, freq, config, i2c_instance)

def create_custom_config(sensor_names, value_names=['RawCount', 'DiffCount'], sensor_address=0x09):
    """
    Create custom sensor configuration
    
    Args:
        sensor_names (list): List of sensor names
        value_names (list): List of value names per sensor
        sensor_address (int): I2C address
    
    Returns:
        dict: Configuration dictionary
    """
    return {
        'sensor_address': sensor_address,
        'register': 0x00,
        'num_sensors': len(sensor_names),
        'values_per_sensor': len(value_names),
        'value_size': 2,
        'sensor_names': sensor_names,
        'value_names': value_names
    }

# Example usage
if __name__ == "__main__":
    # Default configuration
    sensor = create_capsense_reader()
    for i in range(6):
        print(sensor.get_csv_string())
        print('--------------------------')
        print(sensor.get_raw_data())

