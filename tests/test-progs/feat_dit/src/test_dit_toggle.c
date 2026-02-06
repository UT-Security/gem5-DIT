#include <stdio.h>
#include <stdint.h>

static inline void enable_dit(void) {
    __asm__ volatile("msr dit, #1" ::: "memory");
}

static inline void disable_dit(void) {
    __asm__ volatile("msr dit, #0" ::: "memory");
}

static inline uint64_t read_dit(void) {
    uint64_t val;
    __asm__ volatile("mrs %0, dit" : "=r"(val));
    return val;
}

int main(void) {
    int pass = 1;

    // Test multiple toggles
    for (int i = 0; i < 5; i++) {
        enable_dit();
        if ((read_dit() & 0x1000000) != 0x1000000) {  // DIT is bit 24
            printf("TEST_DIT_TOGGLE: FAIL at enable iteration %d\n", i);
            pass = 0;
            break;
        }

        disable_dit();
        if ((read_dit() & 0x1000000) != 0) {  // DIT is bit 24
            printf("TEST_DIT_TOGGLE: FAIL at disable iteration %d\n", i);
            pass = 0;
            break;
        }
    }

    if (pass) {
        printf("TEST_DIT_TOGGLE: PASS\n");
        return 0;
    }
    return 1;
}
