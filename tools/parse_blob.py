import sys

def read_int16_be(h,l):
    v = ((h & 0xFF) << 8) | (l & 0xFF)
    return v - 0x10000 if v & 0x8000 else v

def decode_payload(payload):
    if len(payload) < 23:
        return None
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
    return {
        'mode':mode,
        'voltage_raw':voltage_raw,
        'voltage_v':voltage_raw/1000,
        'temp_raw':temp_raw,
        'temp_c':temp_raw/10,
        'acc':(accx,accy,accz),
        'gyro':(gyrox,gyroy,gyroz),
        'mag':(magx,magy,magz)
    }

def parse_blob(s):
    parts = [p for p in s.replace('\n',' ').split() if p]
    try:
        b = bytes(int(x,16) for x in parts)
    except Exception as e:
        print('parse error:', e)
        return
    i=0; idx=0
    while i < len(b):
        if b[i] != 0x7E:
            i+=1; continue
        if i+6 > len(b): break
        payload_len = b[i+5]
        end = i+6+payload_len+1
        if end > len(b): break
        pkt = b[i:end]
        payload = pkt[6:6+payload_len]
        print('\nPacket', idx, 'raw:', ' '.join(f"{x:02X}" for x in pkt))
        dec = decode_payload(payload)
        if dec is None:
            print(' payload too short', len(payload))
        else:
            print(' voltage:', dec['voltage_v'],'V', ' temp:', dec['temp_c'],'C')
            print(' acc:', ' '.join(f"{v:.2f}" for v in dec['acc']))
            print(' gyro:', ' '.join(f"{v:.1f}" for v in dec['gyro']))
            print(' mag:', ' '.join(f"{v:.1f}" for v in dec['mag']))
        idx+=1
        i = end

if __name__ == '__main__':
    if len(sys.argv) > 1:
        s = ' '.join(sys.argv[1:])
    else:
        s = sys.stdin.read()
    parse_blob(s)
