extern int send_packet(unsigned address, const unsigned char *payload, unsigned size);
extern void wait_ticks(unsigned ticks);

/* 演示连续赋值合框、重试回环和提前结束，不访问真实硬件。 */
int retry_write(unsigned address, unsigned value)
{
    unsigned char payload[2];
    int status = -1;
    unsigned attempt = 0;
    payload[0] = (unsigned char)value;
    payload[1] = (unsigned char)(value >> 8);

    while (attempt < 3) {
        status = send_packet(address, payload, 2);
        if (status == 0 || status == 2) {
            break;
        }
        if (attempt < 2) {
            wait_ticks(1);
        }
        attempt++;
    }
    return status;
}
