idf_component_register(
    SRCS "main.c"
         "ui_pixel.c"
         "ui_pixel_math.c"
         "seed_story.c"
         "seed_save.c"
         "seed_assets.c"
         "seed_assets_data.c"
         "scene_codec.c"
         "scene_data.c"
         "seed_font.c"
         "demo_seed.c"
    INCLUDE_DIRS "."
    REQUIRES bsp esp_timer nvs_flash
)
