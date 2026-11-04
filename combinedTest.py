# Combined sensor test for Raspberry Pi 5: TSL2591 + DHT22 + BMP280.

# Wiring:
#   - TSL2591 -- hardware I2C bus 1: SDA GPIO2 (physical pin 3), SCL GPIO3 (pin 5)
#   - BMP280  -- software I2C: SDA GPIO17 (physical pin 11), SCL GPIO27 (pin 13)
#   - DHT22   -- single-wire data on GPIO4 (physical pin 7)

import time
from datetime import datetime, timezone

import adafruit_bmp280
import adafruit_bitbangio as bitbangio
import adafruit_dht
import adafruit_tsl2591
import board
import busio

DHT_PIN = board.D4
BMP_SDA_PIN = board.D17  # Physical Pin 11
BMP_SCL_PIN = board.D27  # Physical Pin 13
BMP280_ADDRESS = 0x76
READ_INTERVAL_S = 3.0
CELL_WIDTH = 24  # column width for the per-sensor printout

TSL_GAIN = adafruit_tsl2591.GAIN_LOW
TSL_INTEGRATION_TIME = adafruit_tsl2591.INTEGRATIONTIME_100MS


def init_sensors():
    # Bus 1: Hardware I2C for TSL2591 (Physical Pins 3 & 5)
    i2c_hw = busio.I2C(board.SCL, board.SDA)
    tsl = adafruit_tsl2591.TSL2591(i2c_hw)
    tsl.gain = TSL_GAIN
    tsl.integration_time = TSL_INTEGRATION_TIME

    # Bus 2: Software I2C for BMP280 (Physical Pins 11 & 13)
    i2c_sw = bitbangio.I2C(BMP_SCL_PIN, BMP_SDA_PIN)
    bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c_sw, address=BMP280_ADDRESS)

    # DHT22 on GPIO 4 (Physical Pin 7)
    dht = adafruit_dht.DHT22(DHT_PIN, use_pulseio=False)

    return i2c_hw, i2c_sw, tsl, bmp, dht


def read_tsl2591(sensor):
    try:
        ch0, ch1 = sensor.raw_luminosity
    except (RuntimeError, ValueError) as error:
        print(f"TSL2591 read error: {error}")
        return None

    try:
        lux = sensor.lux
    except RuntimeError:
        lux = None

    return {"lux": lux, "ch0": ch0, "ch1": ch1}


def read_dht22(device):
    try:
        return {
            "temperature": device.temperature,
            "humidity": device.humidity,
        }
    except Exception as error:
        # Catches RuntimeErrors and any hardware dropouts gracefully
        print(f"DHT22 read error: {error}")
        return None


def read_bmp280(sensor):
    try:
        return {"pressure": sensor.pressure}
    except (RuntimeError, ValueError) as error:
        print(f"BMP280 read error: {error}")
        return None


def fmt(value, spec, unit=""):
    if value is None:
        return "n/a"
    return f"{format(value, spec)} {unit}".rstrip()


def print_sample(ts, seq, light, air, press):
    rows = [
        (
            "TSL2591",
            [
                ("lux", fmt(light.get("lux"), ".2f", "lx")),
                ("ch0 (all light)", fmt(light.get("ch0"), "d")),
                ("ch1 (infrared)", fmt(light.get("ch1"), "d")),
            ],
        ),
        (
            "DHT22",
            [
                ("temp", fmt(air.get("temperature"), ".1f", "C")),
                ("rh (humidity)", fmt(air.get("humidity"), ".1f", "%")),
            ],
        ),
        (
            "BMP280",
            [("pressure", fmt(press.get("pressure"), ".2f", "hPa"))],
        ),
    ]

    print(f"{ts}   sample #{seq:05d}")
    for name, cells in rows:
        line = "".join(f"{label} {value}".ljust(CELL_WIDTH) for label, value in cells)
        print(f"  {name:<8}| {line.rstrip()}")
    print()


def main():
    i2c_hw, i2c_sw, tsl, bmp, dht = init_sensors()

    print("Press Ctrl+C to stop.\n")

    seq = 0
    try:
        while True:
            seq += 1
            ts = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )

            # Safely query each sensor independently with try/except fallbacks
            try:
                light = read_tsl2591(tsl) or {}
            except Exception as e:
                print(f"TSL2591 unexpected failure: {e}")
                light = {}

            try:
                air = read_dht22(dht) or {}
            except Exception as e:
                print(f"DHT22 unexpected failure: {e}")
                air = {}

            try:
                press = read_bmp280(bmp) or {}
            except Exception as e:
                print(f"BMP280 unexpected failure: {e}")
                press = {}

            print_sample(ts, seq, light, air, press)

            time.sleep(READ_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        dht.exit()
        i2c_hw.deinit()
        i2c_sw.deinit()


if __name__ == "__main__":
    main()