import sys

def read_int16_be(high, low):
    v = ((high & 0xFF) << 8) | (low & 0xFF)
    return v - 0x10000 if v & 0x8000 else v

def decode_hk(payload):
    if len(payload) < 23:
        print('payload too short', len(payload))
        return
    mode = payload[0]
    voltage_raw = (payload[1]<<8) | payload[2]
    temp_raw = read_int16_be(payload[3], payload[4])
    accx = read_int16_be(payload[5], payload[6]) / 100
    accy = read_int16_be(payload[7], payload[8]) / 100
    accz = read_int16_be(payload[9], payload[10]) / 100
    gyrox = read_int16_be(payload[11], payload[12]) / 10
    gyroy = read_int16_be(payload[13], payload[14]) / 10
    gyroz = read_int16_be(payload[15], payload[16]) / 10
    magx = read_int16_be(payload[17], payload[18]) / 10
    magy = read_int16_be(payload[19], payload[20]) / 10
    magz = read_int16_be(payload[21], payload[22]) / 10
    print(f'mode: {mode}')
    print(f'voltage_raw: {voltage_raw} -> {voltage_raw/1000:.3f} V')
    print(f'temp_raw: {temp_raw} -> {temp_raw/10:.1f} °C')
    print(f'acc: {accx:.2f}, {accy:.2f}, {accz:.2f} m/s2')
    print(f'gyro: {gyrox:.1f}, {gyroy:.1f}, {gyroz:.1f} °/s')
    print(f'mag: {magx:.1f}, {magy:.1f}, {magz:.1f} µT')

def main():
    if len(sys.argv) > 1:
        s = ' '.join(sys.argv[1:])
    else:
        s = input('hex> ').strip()
    # normalize
    parts = [p for p in s.replace(',', ' ').split() if p]
    try:
        b = bytes(int(x,16) for x in parts)
    except Exception as e:
        print('failed to parse hex:', e)
        return
    if len(b) < 1:
        print('no bytes')
        return
    if b[0] != 0x7E:
        print('warning: header != 0x7E')
    if len(b) < 7:
        print('packet too short')
        return
    payload_len = b[5]
    payload = b[6:6+payload_len]
    print('raw bytes:', ' '.join(f"{x:02X}" for x in b))
    print('payload len', payload_len, 'payload:', ' '.join(f"{x:02X}" for x in payload))
    decode_hk(payload)

if __name__ == '__main__':
    main()
