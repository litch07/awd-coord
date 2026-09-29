# Proxy <-> Laptop serial protocol
USB serial, 115200 baud, newline-delimited JSON, one object per line.

## Proxy -> Laptop
{"t":"ready","msg":"proxy_online"}
{"t":"field_status","node":1,"depth":2048,"stage":900,"soil":1500,"water":true,"override":false,"uptime":123456}
{"t":"pump_status","pumpOn":false,"rain":4095,"voltage":5.02,"current":0.0,"power":0.0,"fault":false,"uptime":123456}
{"t":"heartbeat","node":0}    (node 0 = pump, 1-4 = field)
{"t":"error","msg":"espnow_send_failed"}    (also bad_json, unknown_field_node, unknown_command_type, peer_add_failed)

## Laptop -> Proxy
{"t":"valve","node":1,"open":true}
{"t":"pump","on":true}

## Conversions (from verified firmware)
- depth_cm = 20 - (depth_raw / 4095) * 20   (0 raw = 20 cm, 4095 raw = 0 cm)
- crop stage from stage raw: <1365 VEGETATIVE, <2730 FLOWERING, else RIPENING
- water: true = wet
- Field status every 1 s, heartbeat every 2 s. Node offline after 6 s of silence.
- override=true means the farmer bypassed automation (the field node physically toggles the valve and locks out the system): never command that plot's valve.
- pump_status.fault=true means fault simulation is engaged: the pump is forced off and ignores commands.
- Only one program may open the COM port at a time. The Arduino Serial Monitor must be closed while the coordinator runs.
