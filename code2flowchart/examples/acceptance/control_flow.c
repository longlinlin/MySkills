/* 高风险控制流验收样例，外部函数仅声明，不代表硬件实现。 */
extern void record_value(int value);
extern void after_switch(int value);
extern void after_inner(void);
extern int acquire_resource(void);
extern void release_resource(void);
extern int probe(void);

int for_continue_case(int limit)
{
    int total = 0;
    for (int i = 0; i < limit; i++) {
        if (i == 1) {
            continue;
        }
        total += i;
    }
    return total;
}

int for_break_case(int limit)
{
    int total = 0;
    for (int i = 0; i < limit; i++) {
        if (i == 2) {
            break;
        }
        total += i;
    }
    return total;
}

int switch_in_loop_case(int count, int mode)
{
    while (count > 0) {
        count--;
        switch (mode) {
        case 0:
            record_value(count);
            break;
        case 1:
            continue;
        default:
            record_value(-count);
            break;
        }
        after_switch(count);
    }
    return count;
}

int nested_break_case(int count, int mode)
{
    while (count > 0) {
        for (int i = 0; i < 3; i++) {
            if (mode) {
                break;
            }
            record_value(i);
        }
        after_inner();
        count--;
    }
    return count;
}

int forward_cleanup_case(void)
{
    int result = acquire_resource();
    if (result < 0) {
        goto cleanup;
    }
    record_value(result);
cleanup:
    release_resource();
    return result;
}

int backward_goto_case(int count)
{
retry:
    count--;
    if (count > 0) {
        goto retry;
    }
    return count;
}

int cross_block_goto_case(int mode)
{
    if (mode) {
cleanup:
        release_resource();
        return 0;
    }
    goto cleanup;
}

int short_circuit_and_case(int value)
{
    if (value++ && probe()) {
        return value;
    }
    return -1;
}

int short_circuit_or_case(int value)
{
    if (value-- || probe()) {
        return value;
    }
    return -1;
}

int nested_return_case(int limit, int state)
{
    for (int i = 0; i < limit; i++) {
        while (state > 0) {
            if (state == 1) {
                return 77;
            }
            state--;
        }
    }
    return 0;
}

int infinite_for_case(int limit)
{
    for (int i = 0; ; i++) {
        if (i == limit) {
            break;
        }
    }
    return 0;
}

int do_continue_case(int count)
{
    do {
        count--;
        if (count > 2) {
            continue;
        }
        record_value(count);
    } while (count > 0);
    return count;
}
