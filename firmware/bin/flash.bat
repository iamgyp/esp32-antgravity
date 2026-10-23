@echo off
set PORT=%1
if "%PORT%"=="" set PORT=COM3
echo Flashing Antigravity Buddy firmware to ESP32-S3 on %PORT%...
esptool.py --chip esp32s3 -p %PORT% -b 921600 --before default_reset --after hard_reset write_flash -z --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0000 bootloader.bin 0x8000 partitions.bin 0x10000 firmware.bin
pause
