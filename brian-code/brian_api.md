# API Documentation

## Overview

The Bremote application communicates with the Brian firmware through a REST API. Endpoints are relative to the configured base URL.

## Endpoints

### File System Operations

#### GET `/api/sd`
- Lists contents of root directory
- Returns: JSON array of file/folder objects
- Error codes: 503, 404

#### GET `/api/sd/{path}`
- Gets file content or directory listing
- Headers: `Content-Type` - MIME type of file (for files)
- Returns: File content or JSON directory listing
- Error codes: 503, 404

#### PUT `/api/sd/{path}`
- Creates or updates file/folder
- Body: File content (for files) or empty (for folders)
- Headers: `Content-Type` - MIME type of file
- Returns: Success message
- Error codes: 503, 400

#### DELETE `/api/sd/{path}`
- Deletes file or folder
- Returns: Success message
- Error codes: 503, 404

#### PATCH `/api/sd/{path}`
- Renames file or folder
- Body: New name
- Returns: Success message
- Error codes: 503, 400

### Status Operations

#### GET `/api/status`
- Gets device status
- Returns: JSON object with status information
```javascript
{
  batteryPct: number,    // 0-100
  charging: boolean,     // true when charging
  chargingSlow: boolean, // true for slow charging
  sdCard: string,        // MOUNTED, MOUNTED_USB, INSERTED_NOT_MOUNTED, UNMOUNTING, UNMOUNTED_NOT_REMOVED, IO_ERROR, IO_ERROR_UNMOUNTED_NOT_REMOVED, ERROR
  wifiStatus: string,    // WiFi status, can be OFF, ERR, AP, or STA. Currently only AP is implemented. Number of connected clients makes sense only in AP mode.
  wifiClients: number    // Number of connected WiFi clients (0-3). If more than 3 clients are connected, an icon with a star will be shown on the web, but the limit is 3 clients.
}
```
- Error codes: 500

### Identity

#### GET `/api/identity`
- Returns: JSON `{ "hw": string, "mac": string, "fw": string, "version": string }`
- Purpose: Firmware identity for device verification. Also returns firmware hash for firmware update check.

### Settings Operations

#### GET `/api/settings`
- Fetches all device settings
- Returns: Key-value pairs in `key=value` format (one per line)
- Response parsing handles type conversion (boolean, number, string)
- Error codes: 500

#### POST `/api/settings`
- Updates one or more settings
- Body: Key-value pairs in `key=value` format (one per line)
- Returns: Success/error status
- Error codes: 400, 500

### Program Operations

#### GET `/api/program/status`
- Gets current program status
- Returns: JSON object with program information
```javascript
{
  status: string,        // NOT_STARTED, RUNNING, FINISHED, CRASHED, KILLED
  killEnabled: boolean,  // Whether the program can be killed (interrupt failed)
  file: string,          // Current program file path
}
```
- Error codes: 500

#### POST `/api/program/run`
- Runs a program file
- Body: File path to run
- Returns: Success/error status
- Error codes: 400, 404, 500

#### POST `/api/program/interrupt`
- Interrupts running program (sends SIGINT)
- Returns: Success/error status
- Error codes: 404, 500

#### POST `/api/program/kill`
- Kills running program (sends SIGKILL)
- Returns: Success/error status
- Error codes: 404, 500

### Console Operations

#### GET `/api/program/console/{fromLine}`
- Fetches console lines starting from specified line number
- Returns: New console text or empty if no new lines
- Headers: `Console-Lines-Dropped` - Number of lines dropped due to buffer overflow
- Error codes: 400 (no new lines), 404 (console not available), 500

#### POST `/api/program/console`
- Sends user input to running program
- Body: Plain text input
- Returns: Success/error status
- Error codes: 404 (program not running), 400 (invalid input), 500

### Motor Operations

#### GET `/api/motor/all`
- Gets probe + handler info for all motor ports (A–D)
- Returns: JSON array length 4 where index 0→A, 1→B, 2→C, 3→D; each item:
```javascript
{
  probe: object,   // e.g., { isConnected: boolean, hasHandler: 0|1|2|3, ... }
  handler: object | null // Motor handler state when present
}
```

#### GET `/api/motor/{port}`
- Gets probe + handler info for a single motor port (`A`, `B`, `C`, `D`)
- Returns: JSON `{ probe: object, handler: object|null }`

#### POST `/api/motor/{port}/{handlerType}`
- Creates a Wi‑Fi handler for the port
- `handlerType`: `autodetect`, `EV3LargeMotor`, `EV3MediumMotor`, `NXTMotor`
- Returns: JSON `{ probe, handler }`

#### POST `/api/motor/{port}`
- Invokes a motor handler method
- Body: `text/plain` with a method call string (e.g., `runAtSpeed(360)`)
- Returns: JSON `{ probe, handler }`

#### DELETE `/api/motor/{port}`
- Releases the Wi‑Fi handler for the port
- Returns: JSON `{ probe, handler }` (handler is typically null)

### Sensor Operations

#### GET `/api/sensor/all`
- Gets probe + handler info for all sensor ports (1–4)
- Returns: JSON array length 4 where index 0→1, 1→2, 2→3, 3→4; each item:
```javascript
{
  probe: object,   // e.g., { isConnected: boolean, hasHandler: 0|1|2|3, info?: { typeCode?: number }, ... }
  handler: object | null // Sensor handler state when present; normalized to include .name
}
```

#### GET `/api/sensor/{port}`
- Gets probe + handler info for a single sensor port (`1`, `2`, `3`, `4`)
- Returns: JSON `{ probe: object, handler: object|null }`

#### POST `/api/sensor/{port}/{handlerName}`
- Creates a Wi‑Fi handler for the port
- `handlerName`: `autodetect` or a specific handler (e.g., `ColorSensorEV3`, `GyroSensorEV3`, `UltrasonicSensorEV3`, `TouchSensorNXT`, etc.)
- Returns: JSON `{ probe, handler }`

#### POST `/api/sensor/{port}`
- Invokes a sensor handler method
- Body: `text/plain` with a method call string (e.g., `setMode(ANGLE)`, `setLedOn(true)`)
- Returns: JSON `{ probe, handler }`

#### DELETE `/api/sensor/{port}`
- Releases the Wi‑Fi handler for the port
- Returns: JSON `{ probe, handler }` (handler is typically null)

## Error Codes

- 400: Bad Request
  - Invalid file name
  - Invalid operation
  - File already exists

- 404: Not Found
  - File/folder doesn't exist
  - Invalid path

- 500: Internal Server Error
  - Server-side error
  - Operation failed

- 503: Service Unavailable
  - SD card not mounted
  - SD card error
  - Device busy

## Response Formats

### Directory Listing
```javascript
[
  {
    name: string,        // File/folder name
    type: string,        // MIME type
    size?: number,       // File size in bytes
    sizeStr?: string,    // Formatted size string
  }
]
```

### Status Response
```javascript
{
  batteryPct: number,    // Battery percentage
  charging: boolean,     // Charging status
  chargingSlow: boolean, // Charging speed
  sdCard: string,        // SD card state
  wifiStatus: string,    // WiFi status
  wifiClients: number    // Number of connected WiFi clients
}
```

### Settings Response
```javascript
// Key-value pairs, one per line
lcdBrightness=100
audioVolume=20
menuClickSoundsEnabled=true
ledIntensity=100
ledEffectEnabled=true
ledEffectColor=0,255,255,255 // Brian color index (0-7), R, G, B
mscEnabled=true
mscNext=true
defaultProgramPath=
shouldRunDefaultOnBoot=false
shouldRunDefaultOnCharger=false
dimAfterS=30
powerOffAfterM=60
shouldAutoPowerOffOnCharger=false
```

### Program Status Response
```javascript
{
  status: string,        // Program status
  killEnabled: boolean,  // Whether the program can be killed (interrupt failed)
  file: string,          // Current program file
}
```

### Console Response
```javascript
// Plain text console output
// Headers: Console-Lines-Dropped: number
```

### Error Response
```javascript
{
  error: string,         // Error message
  code: number           // HTTP status code
}
```

## Usage Examples

### Creating a File
```javascript
await fetch(`${apiUrl}/api/sd/example.txt`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'text/plain'
  },
  body: 'Hello World'
});
```

### Renaming a File
```javascript
await fetch(`${apiUrl}/api/sd/old.txt`, {
  method: 'PATCH',
  body: 'new.txt'
});
```

### Getting Status
```javascript
const response = await fetch(`${apiUrl}/api/status`);
const status = await response.json();
```

### Getting Settings
```javascript
const response = await fetch(`${apiUrl}/api/settings`);
const settingsText = await response.text();
```

### Updating Settings
```javascript
await fetch(`${apiUrl}/api/settings`, {
  method: 'POST',
  body: 'audioVolume=50\nmenuClickSoundsEnabled=false'
});
```

### Getting Program Status
```javascript
const response = await fetch(`${apiUrl}/api/program/status`);
const programStatus = await response.json();
```

### Running a Program
```javascript
await fetch(`${apiUrl}/api/program/run`, {
  method: 'POST',
  body: '/main.py'
});
```

### Getting Console Output
```javascript
const response = await fetch(`${apiUrl}/api/program/console/100`);
const consoleText = await response.text();
const droppedLines = response.headers.get('Console-Lines-Dropped');
```

### Sending Console Input
```javascript
await fetch(`${apiUrl}/api/program/console`, {
  method: 'POST',
  headers: {
    'Content-Type': 'text/plain'
  },
  body: 'print("Hello World")'
});
```

### Getting All Motor Status
```javascript
const motors = await fetch(`${apiUrl}/api/motor/all`).then(r => r.json());
```

### Creating a Motor Handler and Running at Speed
```javascript
await fetch(`${apiUrl}/api/motor/A/autodetect`, { method: 'POST' });
await fetch(`${apiUrl}/api/motor/A`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: 'runAtSpeed(360)' });
```

### Getting All Sensor Status
```javascript
const sensors = await fetch(`${apiUrl}/api/sensor/all`).then(r => r.json());
```

### Creating a Sensor Handler and Changing Mode
```javascript
await fetch(`${apiUrl}/api/sensor/1/ColorSensorEV3`, { method: 'POST' });
await fetch(`${apiUrl}/api/sensor/1`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: 'setMode(AMBIENT)' });
```