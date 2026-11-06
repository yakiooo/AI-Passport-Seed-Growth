// main/main.c —— AI Passport 纯净版固件:初始化 + 开机直接进入 Seed Sim。
//
// 按键语义(全局统一):
//   上/下 短按   选择/移动
//   确定  短按   确认
//   确定  长按   Seed Sim 内部:图鉴/结局页返回主页,游戏页呼出暂停菜单
//
// 线程模型(重要,勿改回):
//   iot_button 的 ADC 轮询跑在 esp_timer 任务里,该任务栈只有 4KB,
//   在回调里建 UI(嵌套几十层 lv_obj_create)会栈溢出踩坏堆。
//   因此 on_key 只把事件写进环形缓冲,由 LVGL 任务里的 key_pump
//   定时器取出分发 —— 建屏/动画/存档全部在 LVGL 任务上下文执行。
#include "bsp_i2c.h"
#include "bsp_display.h"
#include "bsp_button.h"
#include "bsp_audio.h"
#include "bsp_battery.h"
#include "bsp_pins.h"      // 错误日志里要打印 BSP_LCD_* 引脚号
#include "demo.h"
#include "lvgl.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_err.h"
#include "nvs_flash.h"

static const char *TAG = "main";

static const demo_entry_t DEMOS[] = {
    { "Seed Sim",  demo_seed_enter, demo_seed_exit, demo_seed_key },
};
#define DEMO_COUNT (sizeof(DEMOS) / sizeof(DEMOS[0]))

static int s_active = -1;         // 当前所在页;开机即进入第 0 页

// ---- 按键事件环形缓冲(esp_timer 生产 / LVGL 任务消费) ----
typedef struct { uint8_t btn, ev; } key_evt_t;
#define KEY_RING_N 16             // 2 的幂不是必须,但 % 常数编译器会优化
static key_evt_t          s_ring[KEY_RING_N];
static volatile uint8_t   s_head, s_tail;

// 只在 esp_timer 任务里执行:入队,不做任何重活。
static void on_key(bsp_btn_t btn, bsp_btn_ev_t ev, void *user) {
    (void)user;
    uint8_t next = (uint8_t)((s_head + 1) % KEY_RING_N);
    if (next == s_tail) return;             // 队列满:丢弃(长按风暴时保命)
    s_ring[s_head].btn = (uint8_t)btn;
    s_ring[s_head].ev  = (uint8_t)ev;
    s_head = next;
}

// 在 LVGL 任务里执行(lv_timer_handler 持锁期间):取出并分发。
static void key_pump(lv_timer_t *t) {
    (void)t;
    while (s_tail != s_head) {
        key_evt_t e = s_ring[s_tail];
        s_tail = (uint8_t)((s_tail + 1) % KEY_RING_N);
        if (s_active >= 0) {
            DEMOS[s_active].key((bsp_btn_t)e.btn, (bsp_btn_ev_t)e.ev);
        }
    }
}

// ---- NVS 初始化:存档持久化的前提 ----
// 坑记录:少了这一步, nvs_open() 直接返回 ESP_ERR_NVS_NOT_INITIALIZED,
// 而 seed_save.c 里 load/store 的失败分支都是静默的(读不到就用默认值、
// 存不进就返回 false), 表面上"存档代码全对", 实际开关机进度必丢。
// 所以这里必须显式初始化, 并且失败要打出来 —— 不能无声无息。
static bool nvs_storage_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS 分区需要重建(%s), 擦除后重试", esp_err_to_name(err));
        esp_err_t e2 = nvs_flash_erase();
        if (e2 != ESP_OK) {
            ESP_LOGE(TAG, "NVS 擦除失败: %s —— 本次无法保存进度", esp_err_to_name(e2));
            return false;
        }
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS 初始化失败(%s) —— 本次无法保存进度", esp_err_to_name(err));
        return false;
    }
    ESP_LOGI(TAG, "NVS 就绪, 存档持久化可用");
    return true;
}

void app_main(void) {
    ESP_LOGI(TAG, "FoloToy AI Passport BSP demo 启动");
    esp_sleep_wakeup_cause_t wakeup = esp_sleep_get_wakeup_cause();
    if (wakeup != ESP_SLEEP_WAKEUP_UNDEFINED) {
        ESP_LOGI(TAG, "休眠唤醒原因: %d", wakeup);
    }

    bool nvs_ok = nvs_storage_init();

    bsp_i2c_init();
    bsp_i2c_scan();

    // 屏幕是本 demo 的 UI 载体,失败就没有界面可言 —— 打清楚日志后退出。
    if (bsp_display_init() != ESP_OK || !bsp_lvgl_init()) {
        ESP_LOGE(TAG, "显示/LVGL 初始化失败,demo 无法继续。"
                      "检查 SPI 接线(MOSI=%d SCLK=%d CS=%d DC=%d BL=%d)",
                 BSP_LCD_MOSI, BSP_LCD_SCLK, BSP_LCD_CS, BSP_LCD_DC, BSP_LCD_BL);
        return;
    }
    bsp_display_backlight(100);

    // 外设单项失败不阻塞:Seed Sim 的按键/音效会缺,但不影响画面。
    bool btn_ok = (bsp_button_init(on_key, NULL) == ESP_OK);
    bool aud_ok = (bsp_audio_init() == ESP_OK);
    bool bat_ok = (bsp_battery_init() == ESP_OK);
    ESP_LOGI(TAG, "就绪:Button=%d Audio=%d Battery=%d NVS=%d",
             btn_ok, aud_ok, bat_ok, nvs_ok);

    if (bsp_lvgl_lock(1000)) {
        lv_timer_create(key_pump, 30, NULL);   // 按键泵:LVGL 任务里分发
        s_active = 0;
        DEMOS[0].enter();                      // 开机即种子模拟器
        bsp_lvgl_unlock();
    }
}
