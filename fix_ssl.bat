@echo off
REM SSL Certificate Fix for Non-ASCII Paths
REM Run this before starting the bot on Windows

echo Setting up SSL certificate workaround...

REM Set SSL environment variables to use Windows TEMP directory
set SSL_DIR=%TEMP%\ssl_certs
if not exist "%SSL_DIR%" mkdir "%SSL_DIR%"

REM Copy certificate if needed
set CERT_FILE=%SSL_DIR%\cacert.pem
if not exist "%CERT_FILE%" (
    echo Copying SSL certificate to safe location...
    python -c "import certifi, shutil; shutil.copy2(certifi.where(), r'%CERT_FILE%')"
)

REM Set all SSL environment variables
set CURL_CA_BUNDLE=%CERT_FILE%
set REQUESTS_CA_BUNDLE=%CERT_FILE%
set SSL_CERT_FILE=%CERT_FILE%
set HTTPLIB2_CA_CERTS=%CERT_FILE%

echo SSL certificate location: %CERT_FILE%
echo.
echo Starting bot...
python src\main.py

pause
