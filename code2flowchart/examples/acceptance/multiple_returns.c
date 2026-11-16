/* 演示独立返回通道在 End 上方合流，数值只用于验收布局。 */
int select_limit(int enabled, int fault, int temperature, int input)
{
    if (!enabled) {
        return 0;
    }
    if (fault) {
        return -1;
    }
    if (temperature >= 95) {
        return 20;
    }
    if (input < 100) {
        return 60;
    }
    return 200;
}
