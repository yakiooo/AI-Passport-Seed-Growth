// main/seed_save.c —— NVS blob 读写(magic+version, 内容不变不写, 防 Flash 磨损)。
#include "seed_save.h"

#include <string.h>

#include "nvs.h"
#include "nvs_flash.h"

#define SEED_NVS_NS    "seed"
#define SEED_NVS_KEY   "save"
#define SEED_MAGIC     0x53454544u          // "SEED"
#define SEED_VERSION   2u                   // v2: 增加 volume 字段

typedef struct {
    uint32_t magic;
    uint32_t version;
    seed_save_t data;
} seed_blob_t;

static seed_blob_t s_cached;             // 上次写入/读出的内容(用于去重)
static bool        s_cached_valid;

void seed_save_load(seed_save_t *s)
{
    memset(s, 0, sizeof(*s));
    s->volume = SEED_VOL_HIGH;           // 读档失败/旧版本时的默认音量
    nvs_handle_t h;
    if (nvs_open(SEED_NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        seed_blob_t b;
        size_t len = sizeof(b);
        if (nvs_get_blob(h, SEED_NVS_KEY, &b, &len) == ESP_OK &&
            b.magic == SEED_MAGIC && b.version == SEED_VERSION) {
            *s = b.data;
            s_cached = b;
            s_cached_valid = true;
        }
        nvs_close(h);
    }
}

bool seed_save_store(const seed_save_t *s)
{
    seed_blob_t b = { SEED_MAGIC, SEED_VERSION, *s };
    if (s_cached_valid && memcmp(&b, &s_cached, sizeof(b)) == 0) return true;

    if (!s_cached_valid) {               // 首次写前先读一次,避免覆盖未知数据
        seed_save_t tmp;
        seed_save_load(&tmp);
        s_cached_valid = true;
        if (memcmp(&b, &s_cached, sizeof(b)) == 0) return true;
    }

    nvs_handle_t h;
    if (nvs_open(SEED_NVS_NS, NVS_READWRITE, &h) != ESP_OK) return false;
    bool ok = (nvs_set_blob(h, SEED_NVS_KEY, &b, sizeof(b)) == ESP_OK &&
               nvs_commit(h) == ESP_OK);
    nvs_close(h);
    if (ok) { s_cached = b; s_cached_valid = true; }
    return ok;
}

bool seed_ending_unlocked(const seed_save_t *s, int ending_id)
{
    if (ending_id < 1 || ending_id > SEED_ENDING_COUNT) return false;
    return (s->unlocked_mask & (1u << (ending_id - 1))) != 0;
}

bool seed_ending_unlock(seed_save_t *s, int ending_id, bool *is_new)
{
    *is_new = false;
    if (ending_id < 1 || ending_id > SEED_ENDING_COUNT) return false;
    if (ending_id == SEED_HIDDEN_ENDING) {
        uint16_t normal_mask = (1u << (SEED_ENDING_COUNT - 1)) - 1;  // 低 12 位
        if ((s->unlocked_mask & normal_mask) != normal_mask) return false;
    }
    uint16_t bit = 1u << (ending_id - 1);
    if (s->unlocked_mask & bit) return true;
    s->unlocked_mask |= bit;
    s->unlock_play[ending_id] = (uint16_t)s->play_count;
    *is_new = true;
    return true;
}
