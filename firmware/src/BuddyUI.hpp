#pragma once

#include "LGFX_Config.hpp"
#include <math.h>
#include <esp_heap_caps.h>

enum BuddyState {
    STATE_IDLE,
    STATE_THINKING,
    STATE_APPROVAL,
    STATE_SUCCESS,
    STATE_ERROR
};

struct BokehParticle {
    float x;
    float y;
    float speedY;
    float radius;
    float phase;
};

struct BinaryColumn {
    int x;
    float yOffset;
    float speed;
    uint16_t seed;
};

// Robot bounding box dimensions for PSRAM RGB565 + Alpha8 pre-baked poses
static constexpr int BOT_BOX_X = 56;
static constexpr int BOT_BOX_Y = 14;
static constexpr int BOT_BOX_W = 208;
static constexpr int BOT_BOX_H = 198;

class BuddyUI {
public:
    LGFX_Lichuang tft;
    LGFX_Sprite   canvas;

    BuddyState currentState = STATE_IDLE;
    String statusText = "Antigravity Ready";
    String approvalPrompt = "Deploy to Production?";

    int quotaPct = 93;
    char quotaStr[24] = "GEMINI 93%";
    char quotaGem[24] = "93% / 84%";
    char quotaCla[24] = "100% / 100%";
    char quotaArg[24] = "84%";
    bool showHoloDashboard = false;
    int activeHoloTab = 0; // 0: Quota, 1: Weather
    int startTouchX = -1;
    int startTouchY = -1;

    // Weather Data
    char weatherCity[16] = "Hangzhou";
    char weatherTemp[12] = "19C";
    char weatherText[16] = "Sunny";
    char weatherRange[16] = "13~21C";
    char weatherHum[12] = "61%";
    int weatherIcon = 0; // 0: Sun, 1: Cloud, 2: Fog, 3: Rain, 4: Snow, 5: Thunder

    void setQuota(int pct, const char* qStr, const char* qGem, const char* qCla, const char* qArg) {
        if (pct >= 0 && pct <= 100) quotaPct = pct;
        if (qStr && qStr[0]) { strncpy(quotaStr, qStr, sizeof(quotaStr) - 1); quotaStr[sizeof(quotaStr) - 1] = 0; }
        if (qGem && qGem[0]) { strncpy(quotaGem, qGem, sizeof(quotaGem) - 1); quotaGem[sizeof(quotaGem) - 1] = 0; }
        if (qCla && qCla[0]) { strncpy(quotaCla, qCla, sizeof(quotaCla) - 1); quotaCla[sizeof(quotaCla) - 1] = 0; }
        if (qArg && qArg[0]) { strncpy(quotaArg, qArg, sizeof(quotaArg) - 1); quotaArg[sizeof(quotaArg) - 1] = 0; }
    }

    void setWeather(const char* city, const char* temp, const char* text, const char* range, const char* hum, int icon) {
        if (city && city[0]) { strncpy(weatherCity, city, sizeof(weatherCity) - 1); weatherCity[sizeof(weatherCity) - 1] = 0; }
        if (temp && temp[0]) { strncpy(weatherTemp, temp, sizeof(weatherTemp) - 1); weatherTemp[sizeof(weatherTemp) - 1] = 0; }
        if (text && text[0]) { strncpy(weatherText, text, sizeof(weatherText) - 1); weatherText[sizeof(weatherText) - 1] = 0; }
        if (range && range[0]) { strncpy(weatherRange, range, sizeof(weatherRange) - 1); weatherRange[sizeof(weatherRange) - 1] = 0; }
        if (hum && hum[0]) { strncpy(weatherHum, hum, sizeof(weatherHum) - 1); weatherHum[sizeof(weatherHum) - 1] = 0; }
        if (icon >= 0) weatherIcon = icon;
    }

    // Pre-baked PSRAM buffers
    uint16_t* bgBuffers[3]    = {nullptr, nullptr, nullptr}; // 0: Cyan, 1: Gold, 2: Red (320x240x2)
    uint16_t* botColor[4]     = {nullptr, nullptr, nullptr, nullptr}; // 4 arm poses (BOT_BOX_W * BOT_BOX_H * 2)
    uint8_t*  botAlpha[4]     = {nullptr, nullptr, nullptr, nullptr}; // 8-bit SDF coverage (BOT_BOX_W * BOT_BOX_H)

    // Eye gaze & blink physics
    float eyeX = 0.0f;
    float eyeY = 0.0f;
    float eyeTargetX = 0.0f;
    float eyeTargetY = 0.0f;
    float blinkProgress = 0.0f;
    bool  isBlinking = false;
    bool  doubleBlinkPending = false;
    unsigned long nextBlinkTime = 0;
    unsigned long nextLookTime = 0;

    // Scene particles & binary streams
    static constexpr int NUM_BOKEH = 12;
    BokehParticle bokeh[NUM_BOKEH];

    static constexpr int NUM_BIN_COLS = 8;
    BinaryColumn binCols[NUM_BIN_COLS];

    // Touch state
    int lastTouchX = -1;
    int lastTouchY = -1;
    bool isTouching = false;
    unsigned long tapRevertTime = 0;
    unsigned long lastTouchActionTime = 0;
    float touchRippleR = 0.0f;

    // Auto-Dimming & Power Saving (1 min idle dim)
    static constexpr uint8_t BRIGHTNESS_ACTIVE = 250;
    static constexpr uint8_t BRIGHTNESS_DIM    = 15;  // Ultra-gentle ambient level (approx 6%)
    unsigned long dimTimeoutMs = 60 * 1000UL;         // 1 minute (60 seconds)
    unsigned long lastActivityTime = 0;
    float currentBrightness = 250.0f;
    uint8_t targetBrightness = 250;
    bool isDimmed = false;

    void recordActivity() {
        lastActivityTime = millis();
        targetBrightness = BRIGHTNESS_ACTIVE;
        if (isDimmed) {
            isDimmed = false;
            Serial.println("[Power] Activity detected -> Screen Waking Up!");
        }
    }

    void setDimTimeout(unsigned long ms) {
        if (ms > 0) dimTimeoutMs = ms;
    }

    void updateBrightness(unsigned long now) {
        if (lastActivityTime == 0) lastActivityTime = now;

        if (now - lastActivityTime >= dimTimeoutMs) {
            targetBrightness = BRIGHTNESS_DIM;
            if (!isDimmed) {
                isDimmed = true;
                Serial.printf("[Power] Idle %lu s reached -> Screen Dimming to %d\n", (now - lastActivityTime) / 1000, BRIGHTNESS_DIM);
            }
        } else {
            targetBrightness = BRIGHTNESS_ACTIVE;
        }

        float diff = (float)targetBrightness - currentBrightness;
        if (abs(diff) > 0.5f) {
            currentBrightness += diff * 0.08f;
            tft.setBrightness((uint8_t)(currentBrightness + 0.5f));
        }
    }

    // Color helpers for LovyanGFX swap565 format
    static inline float clampf(float x, float a, float b) {
        return x < a ? a : (x > b ? b : x);
    }

    static inline float smoothstepf(float e0, float e1, float x) {
        float t = clampf((x - e0) / (e1 - e0), 0.0f, 1.0f);
        return t * t * (3.0f - 2.0f * t);
    }

    static inline float mixf(float a, float b, float t) {
        return a + (b - a) * t;
    }

    static inline uint16_t packSwap565(int r, int g, int b) {
        r = r < 0 ? 0 : (r > 255 ? 255 : r);
        g = g < 0 ? 0 : (g > 255 ? 255 : g);
        b = b < 0 ? 0 : (b > 255 ? 255 : b);
        uint16_t rgb = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
        return __builtin_bswap16(rgb);
    }

    static inline void unpackSwap565(uint16_t raw, int& r, int& g, int& b) {
        uint16_t v = __builtin_bswap16(raw);
        r = ((v >> 11) & 0x1F) << 3;
        g = ((v >> 5)  & 0x3F) << 2;
        b = (v & 0x1F) << 3;
    }

    static inline void mixRGB(int r1, int g1, int b1, int r2, int g2, int b2, float t, int& ro, int& go, int& bo) {
        t = clampf(t, 0.0f, 1.0f);
        ro = (int)(r1 + (r2 - r1) * t);
        go = (int)(g1 + (g2 - g1) * t);
        bo = (int)(b1 + (b2 - b1) * t);
    }

    static inline void addGlowRGB(int& r, int& g, int& b, int gr, int gg, int gb, float intensity) {
        intensity = clampf(intensity, 0.0f, 1.0f);
        r = min(255, r + (int)(gr * intensity));
        g = min(255, g + (int)(gg * intensity));
        b = min(255, b + (int)(gb * intensity));
    }

    static inline float sdRoundBox(float px, float py, float bx, float by, float r) {
        float qx = fabsf(px) - bx + r;
        float qy = fabsf(py) - by + r;
        float mx = max(qx, 0.0f);
        float my = max(qy, 0.0f);
        return sqrtf(mx * mx + my * my) + min(max(qx, qy), 0.0f) - r;
    }

    static inline float sdSegment(float px, float py, float ax, float ay, float bx, float by) {
        float pax = px - ax, pay = py - ay;
        float bax = bx - ax, bay = by - ay;
        float h = clampf((pax * bax + pay * bay) / max(bax * bax + bay * bay, 0.0001f), 0.0f, 1.0f);
        float dx = pax - bax * h;
        float dy = pay - bay * h;
        return sqrtf(dx * dx + dy * dy);
    }

    static inline void armor3DColor(float nx, float ny, int& ro, int& go, int& bo) {
        float nz2 = max(0.0f, 1.0f - nx * nx - ny * ny);
        float nz = sqrtf(nz2);

        // Key light from top-left-front
        float diff = max(0.0f, nx * (-0.40f) + ny * (-0.52f) + nz * 0.75f);
        // Specular highlight
        float hdot = max(0.0f, nx * (-0.20f) + ny * (-0.26f) + nz * 0.94f);
        float spec = powf(hdot, 24.0f);
        // Rim light
        float rim = (1.0f - nz) * (1.0f - nz);

        float d_pow = powf(diff, 0.74f);
        float r = mixf(92.0f, 240.0f, d_pow) + spec * 58.0f;
        float g = mixf(122.0f, 247.0f, d_pow) + spec * 58.0f;
        float b = mixf(164.0f, 255.0f, d_pow) + spec * 58.0f;

        if (nx > 0.05f || ny > 0.15f) {
            r = mixf(r, 55.0f, rim * 0.48f);
            g = mixf(g, 195.0f, rim * 0.48f);
            b = mixf(b, 255.0f, rim * 0.48f);
        } else {
            r = mixf(r, 255.0f, rim * 0.35f);
            g = mixf(g, 255.0f, rim * 0.35f);
            b = mixf(b, 255.0f, rim * 0.35f);
        }

        ro = (int)clampf(r, 0.0f, 255.0f);
        go = (int)clampf(g, 0.0f, 255.0f);
        bo = (int)clampf(b, 0.0f, 255.0f);
    }

    void init() {
        tft.init();
        tft.setRotation(1); // 320 x 240
        tft.setBrightness(255);
        tft.fillScreen(TFT_BLACK);

        canvas.setColorDepth(16);
        canvas.createSprite(320, 240);
        canvas.setTextDatum(textdatum_t::middle_center);

        // Initialize ambient particles & binary columns
        int colsX[NUM_BIN_COLS] = {14, 26, 38, 48, 272, 282, 294, 306};
        for (int i = 0; i < NUM_BIN_COLS; i++) {
            binCols[i].x = colsX[i];
            binCols[i].yOffset = random(0, 100);
            binCols[i].speed = 0.45f + (random(0, 40) / 100.0f);
            binCols[i].seed = random(100, 9999);
        }

        for (int i = 0; i < NUM_BOKEH; i++) {
            bokeh[i].x = (i < 6) ? random(20, 90) : random(230, 300);
            bokeh[i].y = random(24, 210);
            bokeh[i].speedY = 0.25f + (random(0, 35) / 100.0f);
            bokeh[i].radius = 1.6f + (random(0, 16) / 10.0f);
            bokeh[i].phase = random(0, 628) / 100.0f;
        }

        // Pre-bake 3D SDF backgrounds & robot poses into 8MB PSRAM
        bakeBackgrounds();
        bakeRobotPoses();
        Serial.println("[UI] 3D SDF Robot & HUD Engine initialized in PSRAM!");
    }

    void setState(BuddyState state, const String& msg = "") {
        if (state != STATE_IDLE || currentState != state) {
            recordActivity();
        }
        currentState = state;
        if (msg.length() > 0) {
            if (state == STATE_APPROVAL) {
                approvalPrompt = msg;
            } else {
                statusText = msg;
            }
        }
    }

    int checkTouch() {
        uint16_t x, y;
        unsigned long now = millis();
        bool touched = tft.getTouch(&x, &y);

        if (touched) {
            recordActivity();
            lastTouchX = x;
            lastTouchY = y;

            if (!isTouching) {
                // === INSTANT TOUCH DOWN RESPONSE ===
                isTouching = true;
                startTouchX = x;
                startTouchY = y;
                touchRippleR = 6.0f;

                if (currentState == STATE_APPROVAL) {
                    if (now - lastTouchActionTime > 300) {
                        if (x >= 20 && x <= 155 && y >= 170 && y <= 235) {
                            lastTouchActionTime = now;
                            return 1;
                        }
                        if (x >= 165 && x <= 300 && y >= 170 && y <= 235) {
                            lastTouchActionTime = now;
                            return 2;
                        }
                    }
                } else {
                    if (!showHoloDashboard) {
                        // Open dashboard IMMEDIATELY on touch down (zero release lag!)
                        if (now - lastTouchActionTime > 250) {
                            showHoloDashboard = true;
                            lastTouchActionTime = now;
                            return 3;
                        }
                    } else {
                        // Direct tab / footer buttons respond on touch down!
                        if (now - lastTouchActionTime > 250) {
                            if (y >= 118 && y <= 144) {
                                if (x < 160) activeHoloTab = 0;
                                else activeHoloTab = 1;
                                lastTouchActionTime = now;
                                return 3;
                            } else if (y >= 216) {
                                showHoloDashboard = false;
                                lastTouchActionTime = now;
                                return 3;
                            }
                        }
                    }
                }
            } else {
                // Ongoing touch: real-time swipe detection without waiting for release!
                if (showHoloDashboard && (now - lastTouchActionTime > 280)) {
                    int dx = lastTouchX - startTouchX;
                    if (abs(dx) > 30) {
                        activeHoloTab = (dx < 0) ? 1 : 0;
                        startTouchX = lastTouchX;
                        lastTouchActionTime = now;
                        return 3;
                    }
                }
            }
        } else {
            if (isTouching) {
                // === TOUCH RELEASE ===
                int dx = lastTouchX - startTouchX;
                int absDx = abs(dx);

                if (showHoloDashboard && (now - lastTouchActionTime > 200)) {
                    if (absDx > 25) {
                        activeHoloTab = (dx < 0) ? 1 : 0;
                        lastTouchActionTime = now;
                    } else if (startTouchY > 144 && startTouchY < 216) {
                        // Tap in middle content area flips tab
                        activeHoloTab = (activeHoloTab == 0) ? 1 : 0;
                        lastTouchActionTime = now;
                    }
                }
                isTouching = false;
            }
        }
        return 0;
    }

    void update() {
        unsigned long now = millis();
        updateBrightness(now);

        if (tapRevertTime > 0 && now > tapRevertTime) {
            tapRevertTime = 0;
            setState(STATE_IDLE, "Antigravity Ready");
        }

        uint16_t* fb = (uint16_t*)canvas.getBuffer();
        if (!fb) return;

        // 1. Copy pre-baked SDF radial space + radar bezel background from PSRAM (0.7ms)
        int themeIdx = (currentState == STATE_THINKING) ? 1 : ((currentState == STATE_ERROR) ? 2 : 0);
        if (bgBuffers[themeIdx]) {
            memcpy(fb, bgBuffers[themeIdx], 320 * 240 * sizeof(uint16_t));
        }

        // 2. Render Real-Time Scrolling Binary Matrix Rain & Rotating Radar Nodes
        drawDynamicHUD(fb, now, themeIdx);

        // 3. Compute Robot Hover & Arm Wave Pose
        float hoverF = 0.0f;
        int poseIdx = 1;
        if (currentState == STATE_APPROVAL) {
            hoverF = -7.0f + sinf(now * 0.004f) * 1.5f;
            poseIdx = 1;
        } else if (currentState == STATE_SUCCESS) {
            hoverF = -4.0f + sinf(now * 0.015f) * 4.5f;
            poseIdx = 3; // Both arms raised high in celebration! \o/
        } else if (currentState == STATE_THINKING) {
            hoverF = sinf(now * 0.006f) * 2.0f;
            float w = sinf(now * 0.008f);
            poseIdx = (w < -0.33f) ? 0 : ((w > 0.33f) ? 2 : 1);
        } else if (currentState == STATE_ERROR) {
            hoverF = ((now / 90) % 2 == 0) ? -1.0f : 1.0f;
            poseIdx = 1;
        } else {
            // IDLE: Smooth breathing + friendly hand waving
            hoverF = sinf(now * 0.0035f) * 2.5f;
            float w = sinf(now * 0.0065f);
            poseIdx = (w < -0.35f) ? 0 : ((w > 0.35f) ? 2 : 1);
        }
        int hoverY = (int)roundf(hoverF);

        // 4. Draw Floor Shadow (when not hidden by approval console)
        if (currentState != STATE_APPROVAL) {
            drawFloorShadow(fb, hoverY);
        }

        // 5. Alpha-Composite 3D SDF Phong-Shaded Robot Body Pose onto Framebuffer
        blitRobotPose(fb, poseIdx, BOT_BOX_X, BOT_BOX_Y + hoverY);

        // 6. Real-Time Expanding Antenna Radio Wave Rings & Chest Scanner
        drawAntennaWavesAndChest(fb, now, hoverY, themeIdx);

        // 7. Real-Time Sub-Pixel SDF Visor Facial Expression Shader (Eyes, Brows, Mouth, Glass Sheen)
        updateEyePhysics(now);
        renderVisorFaceSDF(fb, now, hoverY);

        // 8. Celebration Sparkle Stars in STATE_SUCCESS
        if (currentState == STATE_SUCCESS) {
            drawCelebrationStars(now, hoverY);
        }

        // 9. Foreground Holographic Overlays (Approval Console OR Holographic Dashboard OR Status Pill & Telemetry)
        if (currentState == STATE_APPROVAL) {
            drawApprovalHologram(fb, now);
        } else if (showHoloDashboard) {
            drawHoloDashboard(fb, now);
            drawTelemetryTopBar(fb, now, themeIdx);
        } else {
            drawTelemetryAndStatusPill(fb, now, themeIdx);
        }

        canvas.pushSprite(&tft, 0, 0);
    }

private:
    void bakeBackgrounds() {
        const int hudCols[3][3] = {
            {0, 210, 255},   // 0: Cyber Cyan
            {255, 200, 40},  // 1: Cyber Gold
            {255, 70, 50}    // 2: Alert Red
        };

        for (int t = 0; t < 3; t++) {
            bgBuffers[t] = (uint16_t*)heap_caps_malloc(320 * 240 * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
            if (!bgBuffers[t]) continue;

            int hr = hudCols[t][0], hg = hudCols[t][1], hb = hudCols[t][2];

            for (int y = 0; y < 240; y++) {
                for (int x = 0; x < 320; x++) {
                    float dx = x - 160.0f;
                    float dy = y - 115.0f;
                    float dist_norm = sqrtf((dx / 145.0f) * (dx / 145.0f) + (dy / 118.0f) * (dy / 118.0f));
                    float k = clampf(1.0f - dist_norm * 0.85f, 0.0f, 1.0f);
                    float k2 = k * k;

                    int r, g, b;
                    if (t == 2) {
                        r = (int)mixf(6.0f, 52.0f, k2);
                        g = (int)mixf(4.0f, 14.0f, k2);
                        b = (int)mixf(14.0f, 28.0f, k2);
                    } else {
                        r = (int)mixf(2.0f, 16.0f, k2);
                        g = (int)mixf(6.0f, 72.0f, k2);
                        b = (int)mixf(18.0f, 136.0f, k2);
                    }

                    float rad = sqrtf(dx * dx + dy * dy);
                    float ang = fmodf(atan2f(dy, dx) * 57.2957795f + 360.0f, 360.0f);

                    // Ring 1: r = 106
                    float d_r1 = fabsf(rad - 106.0f);
                    if (d_r1 < 1.2f) {
                        addGlowRGB(r, g, b, hr, hg, hb, (1.0f - d_r1 / 1.2f) * 0.24f);
                    }

                    // Ring 2: r = 98 (thick segmented arcs)
                    float d_r2 = fabsf(rad - 98.0f);
                    if (d_r2 < 2.0f) {
                        if ((ang >= 132.0f && ang <= 228.0f) || ang >= 312.0f || ang <= 48.0f) {
                            addGlowRGB(r, g, b, hr, hg, hb, smoothstepf(2.0f, 0.4f, d_r2) * 0.44f);
                        }
                    }

                    // Ring 3: r = 91
                    float d_r3 = fabsf(rad - 91.0f);
                    if (d_r3 < 1.1f) {
                        addGlowRGB(r, g, b, hr, hg, hb, (1.0f - d_r3 / 1.1f) * 0.30f);
                    }

                    // Ring 4: Degree ticks r = 84..89.5
                    if (rad >= 84.0f && rad <= 89.5f) {
                        if ((ang >= 125.0f && ang <= 235.0f) || ang >= 305.0f || ang <= 55.0f) {
                            float rem = fmodf(ang, 4.0f);
                            float dist_ang = min(rem, 4.0f - rem) * (rad * 0.01745f);
                            float rem16 = fmodf(ang, 16.0f);
                            bool is_major = min(rem16, 16.0f - rem16) < 0.8f;
                            float max_r = is_major ? 89.2f : 87.5f;
                            if (rad <= max_r && dist_ang < 0.9f) {
                                addGlowRGB(r, g, b, hr, hg, hb, (1.0f - dist_ang / 0.9f) * (is_major ? 0.50f : 0.25f));
                            }
                        }
                    }

                    // Ring 5: Inner segmented arc r = 80
                    float d_r5 = fabsf(rad - 80.0f);
                    if (d_r5 < 1.5f) {
                        if ((ang >= 148.0f && ang <= 212.0f) || ang >= 328.0f || ang <= 32.0f) {
                            addGlowRGB(r, g, b, 0, 210, 255, smoothstepf(1.5f, 0.2f, d_r5) * 0.34f);
                        }
                    }

                    bgBuffers[t][y * 320 + x] = packSwap565(r, g, b);
                }
            }
        }
    }

    static void blendPixelToBuf(uint16_t* colBuf, uint8_t* alpBuf, int x, int y, int r, int g, int b, float cov) {
        int lx = x - BOT_BOX_X;
        int ly = y - BOT_BOX_Y;
        if (lx < 0 || lx >= BOT_BOX_W || ly < 0 || ly >= BOT_BOX_H) return;
        cov = clampf(cov, 0.0f, 1.0f);
        if (cov <= 0.005f) return;

        int idx = ly * BOT_BOX_W + lx;
        float prevA = alpBuf[idx] / 255.0f;
        int pr = 0, pg = 0, pb = 0;
        if (prevA > 0.0f) {
            unpackSwap565(colBuf[idx], pr, pg, pb);
        }

        float outA = cov + prevA * (1.0f - cov);
        if (outA > 0.001f) {
            int nr = (int)((r * cov + pr * prevA * (1.0f - cov)) / outA);
            int ng = (int)((g * cov + pg * prevA * (1.0f - cov)) / outA);
            int nb = (int)((b * cov + pb * prevA * (1.0f - cov)) / outA);
            colBuf[idx] = packSwap565(nr, ng, nb);
            alpBuf[idx] = (uint8_t)clampf(outA * 255.0f, 0.0f, 255.0f);
        }
    }

    static void bakeSDFCapsule(uint16_t* colBuf, uint8_t* alpBuf, float x1, float y1, float x2, float y2, float r1, float r2, bool isDarkJoint) {
        int pad = (int)(max(r1, r2) + 3.0f);
        int x0 = max(BOT_BOX_X, (int)(min(x1, x2) - pad));
        int xEnd = min(BOT_BOX_X + BOT_BOX_W - 1, (int)(max(x1, x2) + pad));
        int y0 = max(BOT_BOX_Y, (int)(min(y1, y2) - pad));
        int yEnd = min(BOT_BOX_Y + BOT_BOX_H - 1, (int)(max(y1, y2) + pad));

        float dxLine = x2 - x1;
        float dyLine = y2 - y1;
        float lenSq = max(dxLine * dxLine + dyLine * dyLine, 0.001f);

        for (int y = y0; y <= yEnd; y++) {
            for (int x = x0; x <= xEnd; x++) {
                float pax = x - x1, pay = y - y1;
                float h = clampf((pax * dxLine + pay * dyLine) / lenSq, 0.0f, 1.0f);
                float cx = x1 + dxLine * h;
                float cy = y1 + dyLine * h;
                float r = r1 + (r2 - r1) * h;
                float dx = x - cx, dy = y - cy;
                float dist = sqrtf(dx * dx + dy * dy) - r;
                if (dist < 0.75f) {
                    float cov = smoothstepf(0.75f, -0.55f, dist);
                    float nx = clampf(dx / max(r, 1.0f), -0.95f, 0.95f);
                    float ny = clampf(dy / max(r, 1.0f), -0.95f, 0.95f);
                    int cr, cg, cb;
                    if (isDarkJoint) {
                        float lit = max(0.0f, -0.4f * nx - 0.5f * ny + 0.55f);
                        mixRGB(25, 36, 52, 92, 112, 138, lit, cr, cg, cb);
                    } else {
                        armor3DColor(nx, ny, cr, cg, cb);
                    }
                    blendPixelToBuf(colBuf, alpBuf, x, y, cr, cg, cb, cov);
                }
            }
        }
    }

    static void bakeSDFDisc(uint16_t* colBuf, uint8_t* alpBuf, float cx, float cy, float r,
                            int ir, int ig, int ib, int or_, int og, int ob,
                            bool hasRim, int rr, int rg, int rb) {
        int pad = (int)(r + 3.0f);
        int x0 = max(BOT_BOX_X, (int)(cx - pad));
        int x1 = min(BOT_BOX_X + BOT_BOX_W - 1, (int)(cx + pad));
        int y0 = max(BOT_BOX_Y, (int)(cy - pad));
        int y1 = min(BOT_BOX_Y + BOT_BOX_H - 1, (int)(cy + pad));
        for (int y = y0; y <= y1; y++) {
            for (int x = x0; x <= x1; x++) {
                float d = sqrtf((x - cx) * (x - cx) + (y - cy) * (y - cy)) - r;
                if (d < 0.75f) {
                    float cov = smoothstepf(0.75f, -0.55f, d);
                    float t = clampf((d + r) / max(r, 1.0f), 0.0f, 1.0f);
                    int cr, cg, cb;
                    mixRGB(ir, ig, ib, or_, og, ob, t, cr, cg, cb);
                    if (hasRim && d > -1.3f) {
                        mixRGB(cr, cg, cb, rr, rg, rb, smoothstepf(-1.3f, 0.0f, d), cr, cg, cb);
                    }
                    blendPixelToBuf(colBuf, alpBuf, x, y, cr, cg, cb, cov);
                }
            }
        }
    }

    void bakeRobotPoses() {
        const int numPixels = BOT_BOX_W * BOT_BOX_H;

        // Allocate all 4 poses in PSRAM
        for (int p = 0; p < 4; p++) {
            botColor[p] = (uint16_t*)heap_caps_calloc(numPixels, sizeof(uint16_t), MALLOC_CAP_SPIRAM);
            botAlpha[p] = (uint8_t*)heap_caps_calloc(numPixels, sizeof(uint8_t), MALLOC_CAP_SPIRAM);
        }
        if (!botColor[0] || !botAlpha[0]) return;

        // First, bake the shared core body (wheels, torso, chest, neck, antenna, ear pods, helmet outer shell)
        // into temporary buffers, then combine with each arm configuration!
        uint16_t* coreCol = (uint16_t*)heap_caps_calloc(numPixels, sizeof(uint16_t), MALLOC_CAP_SPIRAM);
        uint8_t*  coreAlp = (uint8_t*)heap_caps_calloc(numPixels, sizeof(uint8_t), MALLOC_CAP_SPIRAM);

        const float head_cx = 160.0f, head_cy = 91.0f;
        const float torso_cx = 160.0f, torso_cy = 164.0f;

        // 1. Wheels & Sculpted Fenders
        float wheelX[2] = {126.0f, 194.0f};
        float wheelSide[2] = {-1.0f, 1.0f};
        for (int w = 0; w < 2; w++) {
            float wx = wheelX[w], side = wheelSide[w], wy = 198.0f;
            for (int y = (int)(wy - 14); y <= (int)(wy + 14); y++) {
                for (int x = (int)(wx - 13); x <= (int)(wx + 13); x++) {
                    float dx = x - wx, dy = y - wy;
                    float d_tire = sdRoundBox(dx, dy, 9.5f, 11.5f, 4.5f);
                    if (d_tire < 0.75f) {
                        float cov = smoothstepf(0.75f, -0.55f, d_tire);
                        int shade = (int)mixf(20.0f, 62.0f, max(0.0f, -dy / 12.0f + 0.5f));
                        int cr = shade, cg = shade + 6, cb = shade + 14;
                        float rdx = (dx - side * 4.2f) / 3.8f;
                        float rdy = dy / 8.5f;
                        float d_rim = fabsf(sqrtf(rdx * rdx + rdy * rdy) - 1.0f) * 4.5f;
                        if (d_rim < 1.3f) {
                            mixRGB(cr, cg, cb, 0, 235, 255, smoothstepf(1.3f, 0.2f, d_rim), cr, cg, cb);
                        }
                        blendPixelToBuf(coreCol, coreAlp, x, y, cr, cg, cb, cov);
                    }
                }
            }
            bakeSDFCapsule(coreCol, coreAlp, wx - side * 2.0f, wy - 10.0f, wx + side * 5.0f, wy - 3.0f, 7.5f, 6.5f, false);
        }

        // 2. Chubby Rounded 3D Belly / Torso
        for (int y = 125; y < 206; y++) {
            for (int x = 105; x < 215; x++) {
                float dy = y - torso_cy;
                float taper = 1.0f - max(0.0f, (torso_cy - y) / 88.0f) * 0.17f;
                float rx = 46.5f * taper;
                float ry = 37.5f;
                float dx = x - torso_cx;
                float d = sdRoundBox(dx, dy, rx, ry, 27.5f);
                if (d < 0.75f) {
                    float cov = smoothstepf(0.75f, -0.55f, d);
                    float nx = clampf(dx / (rx + 4.0f), -0.95f, 0.95f);
                    float ny = clampf(dy / (ry + 4.0f), -0.95f, 0.95f);
                    int cr, cg, cb;
                    armor3DColor(nx, ny, cr, cg, cb);

                    // Horizontal chest seam
                    float seam_y = 154.0f + (dx * dx) * 0.0035f;
                    float d_s1 = fabsf(y - seam_y);
                    if (d_s1 < 1.1f) {
                        mixRGB(cr, cg, cb, 82, 104, 134, smoothstepf(1.1f, 0.0f, d_s1) * 0.85f, cr, cg, cb);
                    }
                    // Side belly seams
                    if (y > seam_y) {
                        float side_x = 26.5f + (y - seam_y) * 0.16f;
                        float d_s2 = fabsf(fabsf(dx) - side_x);
                        if (d_s2 < 1.1f) {
                            mixRGB(cr, cg, cb, 92, 114, 144, smoothstepf(1.1f, 0.0f, d_s2) * 0.80f, cr, cg, cb);
                        }
                    }
                    // Lower belly bumper pad
                    float d_pad = sdRoundBox(dx, dy - 26.0f, 15.0f, 6.5f, 4.0f);
                    if (d_pad < 0.8f) {
                        int pr, pg, pb;
                        mixRGB(140, 162, 190, 195, 212, 232, max(0.0f, -ny + 0.3f), pr, pg, pb);
                        if (fabsf(d_pad) < 0.9f) { pr = 85; pg = 105; pb = 132; }
                        mixRGB(cr, cg, cb, pr, pg, pb, smoothstepf(0.8f, -0.4f, d_pad), cr, cg, cb);
                    }
                    // Chest recessed bezel
                    float d_chest = sdRoundBox(dx, dy + 20.0f, 18.0f, 5.8f, 4.5f);
                    if (d_chest < 0.75f) {
                        int pr, pg, pb;
                        mixRGB(65, 82, 104, 105, 125, 148, clampf((dy + 25.0f) / 10.0f, 0.0f, 1.0f), pr, pg, pb);
                        float d_pill = sdRoundBox(dx + 4.5f, dy + 20.0f, 9.5f, 2.6f, 2.2f);
                        if (d_pill < 1.8f) addGlowRGB(pr, pg, pb, 0, 220, 255, smoothstepf(1.8f, 0.0f, d_pill) * 0.6f);
                        if (d_pill < 0.6f) mixRGB(pr, pg, pb, 160, 252, 255, smoothstepf(0.6f, -0.4f, d_pill), pr, pg, pb);
                        float d_amb = sdRoundBox(dx - 11.0f, dy + 20.0f, 2.8f, 2.5f, 1.5f);
                        if (d_amb < 0.6f) mixRGB(pr, pg, pb, 255, 175, 30, smoothstepf(0.6f, -0.4f, d_amb), pr, pg, pb);
                        mixRGB(cr, cg, cb, pr, pg, pb, smoothstepf(0.75f, -0.4f, d_chest), cr, cg, cb);
                    }

                    blendPixelToBuf(coreCol, coreAlp, x, y, cr, cg, cb, cov);
                }
            }
        }

        // Chest left & right round LEDs
        bakeSDFDisc(coreCol, coreAlp, 131.5f, 144.5f, 3.8f, 180, 255, 255, 0, 210, 255, true, 65, 90, 120);
        bakeSDFDisc(coreCol, coreAlp, 188.5f, 144.5f, 4.2f, 255, 205, 80, 240, 130, 10, true, 60, 75, 95);

        // 3. Neck Ring
        for (int y = 127; y < 137; y++) {
            for (int x = 132; x < 188; x++) {
                float dx = (x - 160.0f) / 26.0f;
                float dy = (y - 132.0f) / 4.5f;
                float d = sqrtf(dx * dx + dy * dy) - 1.0f;
                if (d < 0.15f) {
                    int cr, cg, cb;
                    mixRGB(30, 42, 58, 72, 90, 114, 1.0f - fabsf(dx), cr, cg, cb);
                    blendPixelToBuf(coreCol, coreAlp, x, y, cr, cg, cb, smoothstepf(0.15f, -0.1f, d));
                }
            }
        }

        // 4. Antenna Stem, Base & Tip Bulb
        bakeSDFCapsule(coreCol, coreAlp, 160.0f, 25.0f, 160.0f, 39.0f, 1.8f, 2.4f, false);
        bakeSDFCapsule(coreCol, coreAlp, 155.0f, 42.0f, 165.0f, 42.0f, 4.5f, 4.5f, false);
        bakeSDFDisc(coreCol, coreAlp, 160.0f, 23.0f, 4.2f, 255, 255, 255, 0, 220, 255, false, 0, 0, 0);

        // 5. Ear Pods
        float earX[2] = {94.0f, 226.0f};
        float earSide[2] = {-1.0f, 1.0f};
        for (int e = 0; e < 2; e++) {
            float ex = earX[e], side = earSide[e], ey = head_cy;
            for (int y = (int)(ey - 21); y <= (int)(ey + 21); y++) {
                for (int x = (int)(ex - 9); x <= (int)(ex + 9); x++) {
                    float dx = x - ex, dy = y - ey;
                    float d_ear = sdRoundBox(dx, dy, 6.8f, 18.5f, 5.5f);
                    if (d_ear < 0.75f) {
                        float cov = smoothstepf(0.75f, -0.55f, d_ear);
                        float lit = clampf(-dy / 18.0f * 0.4f + 0.5f, 0.0f, 1.0f);
                        int cr, cg, cb;
                        mixRGB(85, 105, 130, 185, 205, 225, lit, cr, cg, cb);
                        float d_ring = fabsf(sdRoundBox(dx - side * 1.5f, dy, 3.2f, 13.0f, 2.5f));
                        if (d_ring < 1.1f) {
                            mixRGB(cr, cg, cb, 0, 215, 255, smoothstepf(1.1f, 0.1f, d_ring), cr, cg, cb);
                        }
                        blendPixelToBuf(coreCol, coreAlp, x, y, cr, cg, cb, cov);
                    }
                }
            }
        }

        // 6. Helmet Shell & Visor Bezel
        for (int y = 43; y < 139; y++) {
            for (int x = 92; x < 228; x++) {
                float dx = x - head_cx, dy = y - head_cy;
                float top_taper = 1.0f - max(0.0f, -dy / 45.0f) * 0.06f;
                float d_helmet = sdRoundBox(dx / top_taper, dy, 63.0f, 44.5f, 31.5f);
                if (d_helmet < 0.75f) {
                    float cov = smoothstepf(0.75f, -0.55f, d_helmet);
                    float nx = clampf(dx / 65.0f, -0.96f, 0.96f);
                    float ny = clampf(dy / 47.0f, -0.96f, 0.96f);
                    float d_visor = sdRoundBox(dx, dy - 1.0f, 51.0f, 33.5f, 22.0f);

                    int cr, cg, cb;
                    if (d_visor < -1.2f) {
                        // Dark visor placeholder (overdrawn every frame by real-time SDF Visor Shader)
                        cr = 6; cg = 14; cb = 26;
                    } else if (d_visor < 1.5f) {
                        float t_rim = smoothstepf(-1.2f, 1.5f, d_visor);
                        int br, bg_, bb;
                        mixRGB(42, 54, 72, 175, 195, 218, max(0.0f, -0.5f * nx - 0.5f * ny + 0.5f), br, bg_, bb);
                        mixRGB(18, 56, 92, br, bg_, bb, t_rim, cr, cg, cb);
                    } else {
                        armor3DColor(nx, ny, cr, cg, cb);
                        if (dy < -20.0f && fabsf(fabsf(dx) - 34.0f) < 1.0f) {
                            mixRGB(cr, cg, cb, 95, 118, 146, smoothstepf(1.0f, 0.0f, fabsf(fabsf(dx) - 34.0f)) * 0.75f, cr, cg, cb);
                        }
                        float d_corner = sqrtf((fabsf(dx) - 48.0f) * (fabsf(dx) - 48.0f) + (fabsf(dy - 1.0f) - 26.5f) * (fabsf(dy - 1.0f) - 26.5f));
                        if (d_corner < 5.5f) addGlowRGB(cr, cg, cb, 255, 145, 10, smoothstepf(5.5f, 0.0f, d_corner) * 0.65f);
                        if (d_corner < 2.2f) mixRGB(cr, cg, cb, 255, 225, 110, smoothstepf(2.2f, 0.2f, d_corner), cr, cg, cb);
                    }
                    blendPixelToBuf(coreCol, coreAlp, x, y, cr, cg, cb, cov);
                }
            }
        }

        // Now assemble each of the 4 poses: first draw arms, then composite core body on top!
        float waveAngles[3] = {-13.0f, 0.0f, 13.0f};
        for (int p = 0; p < 4; p++) {
            uint16_t* cBuf = botColor[p];
            uint8_t*  aBuf = botAlpha[p];

            if (p < 3) {
                // Waving Right Arm at waveAngles[p]
                float elbowX = 90.0f, elbowY = 131.0f;
                bakeSDFCapsule(cBuf, aBuf, 114.0f, 148.0f, 114.0f, 148.0f, 9.5f, 9.5f, true);
                bakeSDFCapsule(cBuf, aBuf, 108.0f, 145.0f, elbowX + 2.0f, elbowY + 3.0f, 9.5f, 10.5f, false);
                bakeSDFCapsule(cBuf, aBuf, elbowX, elbowY, elbowX, elbowY, 8.2f, 8.2f, true);

                float rad = waveAngles[p] * 0.01745329f;
                float ca = cosf(rad), sa = sinf(rad);
                auto rotX = [&](float dx, float dy) { return elbowX + dx * ca - dy * sa; };
                auto rotY = [&](float dx, float dy) { return elbowY + dx * sa + dy * ca; };

                bakeSDFCapsule(cBuf, aBuf, rotX(-1, -2), rotY(-1, -2), rotX(-10, -20), rotY(-10, -20), 10.2f, 8.8f, false);
                bakeSDFCapsule(cBuf, aBuf, rotX(-13, -27), rotY(-13, -27), rotX(-13, -27), rotY(-13, -27), 7.2f, 7.2f, true);

                const float fDefs[4][5] = {
                    {-19, -28, -27, -33, 2.7f},
                    {-17, -33, -21, -42, 2.8f},
                    {-12, -34, -13, -44, 2.8f},
                    { -7, -32,  -5, -41, 2.6f}
                };
                for (int f = 0; f < 4; f++) {
                    bakeSDFCapsule(cBuf, aBuf,
                                   rotX(fDefs[f][0], fDefs[f][1]), rotY(fDefs[f][0], fDefs[f][1]),
                                   rotX(fDefs[f][2], fDefs[f][3]), rotY(fDefs[f][2], fDefs[f][3]),
                                   fDefs[f][4], fDefs[f][4] * 0.85f, false);
                }

                // Hanging Left Arm
                bakeSDFCapsule(cBuf, aBuf, 206.0f, 148.0f, 206.0f, 148.0f, 9.5f, 9.5f, true);
                bakeSDFCapsule(cBuf, aBuf, 209.0f, 146.0f, 220.0f, 156.0f, 11.2f, 9.8f, false);
                bakeSDFDisc(cBuf, aBuf, 217.5f, 149.5f, 4.2f, 255, 195, 60, 240, 120, 10, true, 70, 45, 20);
                bakeSDFCapsule(cBuf, aBuf, 223.0f, 164.0f, 223.0f, 164.0f, 7.8f, 7.8f, true);
                bakeSDFCapsule(cBuf, aBuf, 225.0f, 168.0f, 229.0f, 184.0f, 10.2f, 8.4f, false);
                bakeSDFDisc(cBuf, aBuf, 228.5f, 174.0f, 3.5f, 180, 255, 255, 0, 200, 255, true, 30, 90, 140);
                bakeSDFCapsule(cBuf, aBuf, 229.0f, 192.0f, 229.0f, 192.0f, 6.2f, 6.2f, true);
                bakeSDFCapsule(cBuf, aBuf, 225.0f, 194.0f, 224.0f, 200.0f, 2.5f, 2.0f, false);
                bakeSDFCapsule(cBuf, aBuf, 230.0f, 195.0f, 229.0f, 202.0f, 2.5f, 2.0f, false);
                bakeSDFCapsule(cBuf, aBuf, 234.0f, 193.0f, 234.0f, 199.0f, 2.4f, 1.9f, false);
            } else {
                // Pose 3: Both Arms Raised High in Joyful Celebration! \o/
                bakeSDFCapsule(cBuf, aBuf, 114.0f, 146.0f, 92.0f, 126.0f, 9.0f, 10.0f, false);
                bakeSDFCapsule(cBuf, aBuf, 90.0f, 124.0f, 78.0f, 98.0f, 9.5f, 8.5f, false);
                bakeSDFCapsule(cBuf, aBuf, 76.0f, 93.0f, 76.0f, 93.0f, 7.0f, 7.0f, true);
                const float lf[4][2] = {{68, 84}, {73, 81}, {78, 81}, {83, 84}};
                for (int f = 0; f < 4; f++) {
                    bakeSDFCapsule(cBuf, aBuf, 76.0f, 91.0f, lf[f][0], lf[f][1], 2.6f, 2.1f, false);
                }

                bakeSDFCapsule(cBuf, aBuf, 206.0f, 146.0f, 228.0f, 126.0f, 9.0f, 10.0f, false);
                bakeSDFCapsule(cBuf, aBuf, 230.0f, 124.0f, 242.0f, 98.0f, 9.5f, 8.5f, false);
                bakeSDFCapsule(cBuf, aBuf, 244.0f, 93.0f, 244.0f, 93.0f, 7.0f, 7.0f, true);
                const float rf[4][2] = {{237, 84}, {242, 81}, {247, 81}, {252, 84}};
                for (int f = 0; f < 4; f++) {
                    bakeSDFCapsule(cBuf, aBuf, 244.0f, 91.0f, rf[f][0], rf[f][1], 2.6f, 2.1f, false);
                }
            }

            // Composite shared core body over the arms
            for (int i = 0; i < numPixels; i++) {
                uint8_t ca = coreAlp[i];
                if (ca == 255) {
                    cBuf[i] = coreCol[i];
                    aBuf[i] = 255;
                } else if (ca > 0) {
                    int r, g, b;
                    unpackSwap565(coreCol[i], r, g, b);
                    int lx = i % BOT_BOX_W;
                    int ly = i / BOT_BOX_W;
                    blendPixelToBuf(cBuf, aBuf, BOT_BOX_X + lx, BOT_BOX_Y + ly, r, g, b, ca / 255.0f);
                }
            }
        }

        heap_caps_free(coreCol);
        heap_caps_free(coreAlp);
    }

    void blitRobotPose(uint16_t* fb, int poseIdx, int dstX, int dstY) {
        uint16_t* cBuf = botColor[poseIdx];
        uint8_t*  aBuf = botAlpha[poseIdx];
        if (!cBuf || !aBuf) return;

        for (int ly = 0; ly < BOT_BOX_H; ly++) {
            int sy = dstY + ly;
            if (sy < 0 || sy >= 240) continue;
            uint16_t* dstRow = &fb[sy * 320];
            int rowOff = ly * BOT_BOX_W;

            for (int lx = 0; lx < BOT_BOX_W; lx++) {
                uint8_t a = aBuf[rowOff + lx];
                if (a == 0) continue;
                int sx = dstX + lx;
                if (sx < 0 || sx >= 320) continue;

                if (a == 255) {
                    dstRow[sx] = cBuf[rowOff + lx];
                } else {
                    int sr, sg, sb, dr, dg, db;
                    unpackSwap565(cBuf[rowOff + lx], sr, sg, sb);
                    unpackSwap565(dstRow[sx], dr, dg, db);
                    int or_ = (sr * a + dr * (255 - a)) >> 8;
                    int og  = (sg * a + dg * (255 - a)) >> 8;
                    int ob  = (sb * a + db * (255 - a)) >> 8;
                    dstRow[sx] = packSwap565(or_, og, ob);
                }
            }
        }
    }

    void drawFloorShadow(uint16_t* fb, int hoverY) {
        float scale = 1.0f - hoverY * 0.02f;
        float rx = 50.0f * scale;
        for (int y = 198; y < 220; y++) {
            for (int x = 104; x < 216; x++) {
                float dx = (x - 160.0f) / rx;
                float dy = (y - 209.0f) / 7.5f;
                float d2 = dx * dx + dy * dy;
                if (d2 < 1.0f) {
                    float sh = (1.0f - d2) * 0.65f;
                    int r, g, b;
                    unpackSwap565(fb[y * 320 + x], r, g, b);
                    r = (int)(r * (1.0f - sh));
                    g = (int)(g * (1.0f - sh));
                    b = (int)(b * (1.0f - sh));
                    fb[y * 320 + x] = packSwap565(r, g, b);
                }
            }
        }
    }

    void drawDynamicHUD(uint16_t* fb, unsigned long now, int themeIdx) {
        // 1. Scrolling Binary Matrix Rain
        float speedMul = (currentState == STATE_THINKING) ? 2.5f : 1.0f;
        canvas.setFont(&fonts::Font0);
        for (int c = 0; c < NUM_BIN_COLS; c++) {
            binCols[c].yOffset += binCols[c].speed * speedMul;
            if (binCols[c].yOffset >= 12.0f) {
                binCols[c].yOffset -= 12.0f;
                binCols[c].seed = (binCols[c].seed * 1103515245 + 12345) & 0x7FFF;
            }
            int bx = binCols[c].x;
            for (int row = 0; row < 14; row++) {
                int by = 26 + row * 12 + (int)binCols[c].yOffset;
                if (by > 202) continue;
                uint16_t h = (binCols[c].seed + row * 37) & 0xFF;
                if (h < 155) {
                    float distY = fabsf(by - 115.0f) / 95.0f;
                    float inten = clampf((1.0f - distY) * ((h & 0x3F) / 64.0f + 0.3f), 0.12f, 0.70f);
                    uint16_t col;
                    if (themeIdx == 2) col = canvas.color565((int)(255 * inten), (int)(80 * inten), (int)(60 * inten));
                    else if (themeIdx == 1 && (h & 3) == 0) col = canvas.color565((int)(255 * inten), (int)(210 * inten), (int)(60 * inten));
                    else col = canvas.color565(0, (int)(195 * inten), (int)(245 * inten));

                    canvas.setTextColor(col);
                    canvas.drawChar((h & 1) ? '1' : '0', bx, by);
                }
            }
        }

        // 2. Drifting Glowing Bokeh Particles
        for (int i = 0; i < NUM_BOKEH; i++) {
            bokeh[i].y -= bokeh[i].speedY * speedMul;
            if (bokeh[i].y < 20.0f) {
                bokeh[i].y = 212.0f;
            }
            float pulse = 0.75f + 0.25f * sinf(now * 0.005f + bokeh[i].phase);
            int px = (int)bokeh[i].x;
            int py = (int)bokeh[i].y;
            int pr = (int)(bokeh[i].radius * 2.2f);
            for (int y = max(0, py - pr); y <= min(239, py + pr); y++) {
                for (int x = max(0, px - pr); x <= min(319, px + pr); x++) {
                    float d = sqrtf((x - bokeh[i].x) * (x - bokeh[i].x) + (y - bokeh[i].y) * (y - bokeh[i].y));
                    if (d < pr) {
                        float g_int = powf(1.0f - d / pr, 1.8f) * pulse * 0.75f;
                        int r, g, b;
                        unpackSwap565(fb[y * 320 + x], r, g, b);
                        if (themeIdx == 2) addGlowRGB(r, g, b, 255, 110, 90, g_int);
                        else if (themeIdx == 1 && (i & 1)) addGlowRGB(r, g, b, 255, 220, 90, g_int);
                        else addGlowRGB(r, g, b, 130, 235, 255, g_int);
                        fb[y * 320 + x] = packSwap565(r, g, b);
                    }
                }
            }
        }

        // 3. Orbiting HUD Radar Telemetry Nodes
        float ang1 = now * (themeIdx == 1 ? 0.0032f : 0.0012f);
        float ang2 = -now * (themeIdx == 1 ? 0.0025f : 0.0009f);
        float nodes[4][2] = {
            {160.0f + cosf(ang1) * 98.0f, 115.0f + sinf(ang1) * 98.0f},
            {160.0f - cosf(ang1) * 98.0f, 115.0f - sinf(ang1) * 98.0f},
            {160.0f + cosf(ang2) * 80.0f, 115.0f + sinf(ang2) * 80.0f},
            {160.0f - cosf(ang2) * 80.0f, 115.0f - sinf(ang2) * 80.0f}
        };
        for (int n = 0; n < 4; n++) {
            int nx = (int)nodes[n][0], ny = (int)nodes[n][1];
            for (int y = max(0, ny - 5); y <= min(239, ny + 5); y++) {
                for (int x = max(0, nx - 5); x <= min(319, nx + 5); x++) {
                    float d = sqrtf((x - nodes[n][0]) * (x - nodes[n][0]) + (y - nodes[n][1]) * (y - nodes[n][1]));
                    if (d < 5.0f) {
                        int r, g, b;
                        unpackSwap565(fb[y * 320 + x], r, g, b);
                        float gi = powf(1.0f - d / 5.0f, 1.6f) * 0.85f;
                        addGlowRGB(r, g, b, 160, 250, 255, gi);
                        fb[y * 320 + x] = packSwap565(r, g, b);
                    }
                }
            }
        }
    }

    void drawAntennaWavesAndChest(uint16_t* fb, unsigned long now, int hoverY, int themeIdx) {
        // 1. Expanding Concentric Radio Wave Ripples from Antenna Tip (160, 23 + hoverY)
        float antX = 160.0f;
        float antY = 23.0f + hoverY;
        float cycle = fmodf(now * (themeIdx == 1 ? 0.015f : 0.008f), 6.0f);

        int hr = (themeIdx == 2) ? 255 : ((themeIdx == 1) ? 255 : 0);
        int hg = (themeIdx == 2) ? 80  : ((themeIdx == 1) ? 210 : 230);
        int hb = (themeIdx == 2) ? 60  : ((themeIdx == 1) ? 50  : 255);

        for (int w = 0; w < 3; w++) {
            float rw = 5.0f + w * 5.5f + fmodf(cycle + w * 2.0f, 5.5f);
            if (rw > 18.0f) continue;
            float fade = clampf(1.0f - (rw - 4.5f) / 14.0f, 0.0f, 1.0f) * 0.72f;
            int y0 = max(0, (int)(antY - rw - 2));
            int y1 = min(239, (int)(antY + rw + 2));
            int x0 = max(0, (int)(antX - rw - 2));
            int x1 = min(319, (int)(antX + rw + 2));

            for (int y = y0; y <= y1; y++) {
                for (int x = x0; x <= x1; x++) {
                    float d = fabsf(sqrtf((x - antX) * (x - antX) + (y - antY) * (y - antY)) - rw);
                    if (d < 1.2f) {
                        int r, g, b;
                        unpackSwap565(fb[y * 320 + x], r, g, b);
                        addGlowRGB(r, g, b, hr, hg, hb, (1.0f - d / 1.2f) * fade);
                        fb[y * 320 + x] = packSwap565(r, g, b);
                    }
                }
            }
        }

        // 2. Animated Chest Scanner & Account Quota Energy Fill (x: 147..164, y: 144 + hoverY)
        int cy = 144 + hoverY;
        int fillW = (int)(17.0f * (quotaPct / 100.0f));
        if (fillW < 2 && quotaPct > 0) fillW = 2;
        int qR = (quotaPct >= 70) ? 0   : ((quotaPct >= 30) ? 255 : 255);
        int qG = (quotaPct >= 70) ? 210 : ((quotaPct >= 30) ? 190 : 70);
        int qB = (quotaPct >= 70) ? 255 : ((quotaPct >= 30) ? 40  : 50);

        for (int y = max(0, cy - 2); y <= min(239, cy + 2); y++) {
            for (int x = 147; x <= 164; x++) {
                int r, g, b;
                unpackSwap565(fb[y * 320 + x], r, g, b);
                if (x <= 147 + fillW) {
                    addGlowRGB(r, g, b, qR, qG, qB, 0.65f);
                } else {
                    r = (int)(r * 0.35f);
                    g = (int)(g * 0.35f);
                    b = (int)(b * 0.35f);
                }
                fb[y * 320 + x] = packSwap565(r, g, b);
            }
        }

        float scanX = 147.5f + fmodf(now * (themeIdx == 1 ? 0.020f : 0.008f), (float)max(4, fillW));
        for (int y = max(0, cy - 3); y <= min(239, cy + 3); y++) {
            for (int x = 146; x <= 165; x++) {
                float d = sqrtf((x - scanX) * (x - scanX) + (y - cy) * (y - cy));
                if (d < 3.2f) {
                    int r, g, b;
                    unpackSwap565(fb[y * 320 + x], r, g, b);
                    addGlowRGB(r, g, b, 255, 255, 255, (1.0f - d / 3.2f) * 0.85f);
                    fb[y * 320 + x] = packSwap565(r, g, b);
                }
            }
        }
    }

    void updateEyePhysics(unsigned long now) {
        if (currentState == STATE_APPROVAL) {
            eyeTargetX = 0.0f;
            eyeTargetY = 3.0f; // Looking down attentively at the approval console
        } else if (currentState == STATE_THINKING) {
            eyeTargetX = sinf(now * 0.007f) * 4.5f;
            eyeTargetY = cosf(now * 0.005f) * 2.5f;
        } else if (now > nextLookTime) {
            eyeTargetX = random(-60, 61) / 10.0f; // -6.0 .. +6.0 px inside visor
            eyeTargetY = random(-35, 36) / 10.0f; // -3.5 .. +3.5 px
            nextLookTime = now + random(1600, 3800);
        }

        eyeX += (eyeTargetX - eyeX) * 0.22f;
        eyeY += (eyeTargetY - eyeY) * 0.22f;

        if (!isBlinking && now > nextBlinkTime) {
            isBlinking = true;
            blinkProgress = 0.0f;
        }
        if (isBlinking) {
            blinkProgress += 0.28f;
            if (blinkProgress >= 1.0f) {
                blinkProgress = 1.0f;
                isBlinking = false;
                if (doubleBlinkPending) {
                    doubleBlinkPending = false;
                    nextBlinkTime = now + 110;
                } else {
                    doubleBlinkPending = (random(0, 100) < 25);
                    nextBlinkTime = now + random(2800, 5600);
                }
            }
        } else if (blinkProgress > 0.0f) {
            blinkProgress -= 0.22f;
            if (blinkProgress < 0.0f) blinkProgress = 0.0f;
        }
    }

    // Real-Time Sub-Pixel SDF Visor Shader (102 x 66 pixels = 6,732 pixels -> ~1.1ms on 240MHz ESP32-S3!)
    void renderVisorFaceSDF(uint16_t* fb, unsigned long now, int hoverY) {
        const float head_cx = 160.0f;
        const float head_cy = 91.0f + hoverY;

        const bool isSucc  = (currentState == STATE_SUCCESS);
        const bool isErr   = (currentState == STATE_ERROR);
        const bool isThink = (currentState == STATE_THINKING);

        const int glowR = isErr ? 255 : (isThink ? 255 : 0);
        const int glowG = isErr ? 65  : (isThink ? 200 : 215);
        const int glowB = isErr ? 45  : (isThink ? 30  : 255);

        const int coreR = isErr ? 255 : (isThink ? 255 : 155);
        const int coreG = isErr ? 195 : (isThink ? 245 : 252);
        const int coreB = isErr ? 175 : (isThink ? 160 : 255);

        float wavePhase = now * 0.018f;
        float eyeScaleY = 1.0f / max(1.0f - blinkProgress * 0.88f, 0.12f);

        int yMin = max(0, (int)(head_cy - 34));
        int yMax = min(239, (int)(head_cy + 36));

        for (int y = yMin; y <= yMax; y++) {
            float dy = y - head_cy;
            uint16_t* rowPtr = &fb[y * 320];

            for (int x = 108; x <= 212; x++) {
                float dx = x - head_cx;
                float d_visor = sdRoundBox(dx, dy - 1.0f, 51.0f, 33.5f, 22.0f);
                if (d_visor >= -1.1f) continue;

                // 1. Base Dark Curved Glass Visor Gradient
                float edge_glow = clampf((d_visor + 11.0f) / 9.8f, 0.0f, 1.0f);
                int vr = (int)mixf(5.0f, 12.0f, edge_glow);
                int vg = (int)mixf(12.0f, 46.0f, edge_glow);
                int vb = (int)mixf(24.0f, 84.0f, edge_glow);

                // Subtle tech dot-matrix texture in bottom-right of visor
                if (dx > 8.0f && dy > 6.0f && ((x & 1) == 0) && ((y & 1) == 0)) {
                    vg += 12;
                    vb += 24;
                }

                // 2. Eyes SDF
                float sideSign = (dx < 0.0f) ? -1.0f : 1.0f;
                float eyeCenterX = sideSign * 25.0f + eyeX;
                float eyeCenterY = 1.5f + eyeY;
                float ex = dx - eyeCenterX;
                float ey = dy - eyeCenterY;

                if (isSucc) {
                    // Happy Arched Crescent Eyes (^ ^) + Rosy Blush Cheeks
                    float d_out = sqrtf(ex * ex + (ey - 3.0f) * (ey - 3.0f)) - 13.5f;
                    float d_in  = sqrtf(ex * ex + (ey - 8.5f) * (ey - 8.5f)) - 11.5f;
                    float d_arch = max(max(d_out, -d_in), ey - 4.0f);
                    if (d_arch < 4.5f && ey < 5.5f) {
                        addGlowRGB(vr, vg, vb, 0, 230, 255, smoothstepf(4.5f, 0.0f, d_arch) * 0.55f);
                    }
                    if (d_arch < 0.7f) {
                        mixRGB(vr, vg, vb, 175, 255, 255, smoothstepf(0.7f, -0.5f, d_arch), vr, vg, vb);
                    }

                    // Coral-Pink Blush Cheeks
                    float bx_blush = (fabsf(dx) - 36.0f) / 1.3f;
                    float by_blush = dy - 11.0f;
                    float d_blush = sqrtf(bx_blush * bx_blush + by_blush * by_blush) - 5.5f;
                    if (d_blush < 4.0f) {
                        addGlowRGB(vr, vg, vb, 255, 80, 150, smoothstepf(4.0f, -2.0f, d_blush) * 0.55f);
                    }
                } else if (isErr) {
                    // Crossed Alert Eyes (> <)
                    float d_x1 = sdSegment(fabsf(ex), ey, -8.5f, -8.5f, 8.5f, 8.5f);
                    float d_x2 = sdSegment(fabsf(ex), ey, -8.5f, 8.5f, 8.5f, -8.5f);
                    float d_x = min(d_x1, d_x2) - 2.1f;
                    if (d_x < 4.5f) addGlowRGB(vr, vg, vb, 255, 60, 40, smoothstepf(4.5f, 0.0f, d_x) * 0.65f);
                    if (d_x < 0.7f) mixRGB(vr, vg, vb, 255, 195, 175, smoothstepf(0.7f, -0.5f, d_x), vr, vg, vb);
                } else {
                    // Standard Glowing Neon Ring Eyes with Blink Squash & 3D Parallax Catchlights
                    float eyScaled = ey * eyeScaleY;
                    float r_eye = sqrtf(ex * ex + eyScaled * eyScaled);

                    if (r_eye < 19.5f) {
                        addGlowRGB(vr, vg, vb, glowR, glowG, glowB, smoothstepf(19.5f, 11.5f, r_eye) * 0.52f);
                    }
                    float d_outer = r_eye - 13.0f;
                    if (d_outer < 0.7f) {
                        mixRGB(vr, vg, vb, coreR, coreG, coreB, smoothstepf(0.7f, -0.5f, d_outer), vr, vg, vb);
                    }
                    float d_pupil = r_eye - 8.4f;
                    if (d_pupil < 0.7f && blinkProgress < 0.75f) {
                        int pr = 8, pg = 26, pb = 52;
                        float d_cres = fabsf(r_eye - 6.0f);
                        if (eyScaled > 1.0f && d_cres < 1.8f) {
                            float ci = smoothstepf(1.8f, 0.0f, d_cres) * smoothstepf(1.0f, 4.0f, eyScaled) * 0.75f;
                            addGlowRGB(pr, pg, pb, glowR, glowG, glowB, ci);
                        }
                        // 3D Parallax Specular Catchlights
                        float spx1 = dx - (sideSign * 25.0f + eyeX * 0.35f) - 3.2f;
                        float spy1 = ey + 3.2f;
                        float d_sp1 = sqrtf(spx1 * spx1 + spy1 * spy1) - 2.6f;
                        if (d_sp1 < 0.7f) {
                            mixRGB(pr, pg, pb, 255, 255, 255, smoothstepf(0.7f, -0.4f, d_sp1), pr, pg, pb);
                        }
                        float spx2 = dx - (sideSign * 25.0f + eyeX * 0.35f) + 3.5f;
                        float spy2 = ey - 3.2f;
                        float d_sp2 = sqrtf(spx2 * spx2 + spy2 * spy2) - 1.2f;
                        if (d_sp2 < 0.7f) {
                            mixRGB(pr, pg, pb, 190, 245, 255, smoothstepf(0.7f, -0.4f, d_sp2), pr, pg, pb);
                        }
                        mixRGB(vr, vg, vb, pr, pg, pb, smoothstepf(0.7f, -0.5f, d_pupil), vr, vg, vb);
                    }
                }

                // 3. Eyebrows SDF (Artifact-free smooth curve with rounded caps!)
                float adx = fabsf(dx);
                float bx = clampf(adx - 25.0f, -8.0f, 8.0f);
                float by_curve;
                if (isThink) {
                    by_curve = -15.0f - bx * 0.22f + eyeY * 0.3f;
                } else if (isErr) {
                    by_curve = -15.5f + bx * 0.24f;
                } else {
                    by_curve = -17.5f + (bx * bx) * 0.065f + eyeY * 0.35f;
                }
                float dbx = (adx - 25.0f) - bx;
                float dby = dy - by_curve;
                float d_brow = sqrtf(dbx * dbx + dby * dby) - 1.55f;
                if (d_brow < 4.0f) addGlowRGB(vr, vg, vb, glowR, glowG, glowB, smoothstepf(4.0f, 0.0f, d_brow) * 0.45f);
                if (d_brow < 0.7f) mixRGB(vr, vg, vb, coreR, coreG, coreB, smoothstepf(0.7f, -0.4f, d_brow), vr, vg, vb);

                // 4. Mouth SDF (Artifact-free smooth smile / real-time neural wave / frown!)
                float mx = clampf(dx, -8.5f, 8.5f);
                float my_curve;
                if (isThink) {
                    // Live dancing neural sine wave oscilloscope!
                    my_curve = 12.0f + sinf(mx * 0.65f + wavePhase) * 2.3f * (1.0f - fabsf(mx) / 11.0f);
                } else if (isErr) {
                    // Worried frown arc
                    my_curve = 10.5f + (mx * mx) * 0.062f;
                } else {
                    // Cute glowing smile arc
                    my_curve = 14.0f - (mx * mx) * 0.065f;
                }
                float dmx = dx - mx;
                float dmy = dy - my_curve;
                float d_mouth = sqrtf(dmx * dmx + dmy * dmy) - 1.65f;
                if (d_mouth < 4.2f) addGlowRGB(vr, vg, vb, glowR, glowG, glowB, smoothstepf(4.2f, 0.0f, d_mouth) * 0.50f);
                if (d_mouth < 0.7f) mixRGB(vr, vg, vb, coreR, coreG, coreB, smoothstepf(0.7f, -0.4f, d_mouth), vr, vg, vb);

                // 5. Diagonal Curved Glass Specular Reflection Sheen (overlaid on visor & eyes!)
                float sheen_c = dx * 0.72f + dy * 1.05f;
                if (sheen_c > -38.0f && sheen_c < -6.0f) {
                    float sh = 1.0f - fabsf(sheen_c + 22.0f) / 16.0f;
                    addGlowRGB(vr, vg, vb, 32, 46, 62, sh * sh);
                }

                rowPtr[x] = packSwap565(vr, vg, vb);
            }
        }
    }

    void drawCelebrationStars(unsigned long now, int hoverY) {
        int starCoords[4][2] = {{56, 65}, {264, 65}, {68, 155}, {252, 155}};
        for (int i = 0; i < 4; i++) {
            int sx = starCoords[i][0];
            int sy = starCoords[i][1] + hoverY;
            int r = (((now / 160) + i) & 1) ? 7 : 4;
            canvas.drawLine(sx - r, sy, sx + r, sy, 0xFFE0);
            canvas.drawLine(sx, sy - r, sx, sy + r, 0xFFE0);
            canvas.fillCircle(sx, sy, 2, TFT_WHITE);
        }
    }

    void drawApprovalHologram(uint16_t* fb, unsigned long now) {
        // Translucent Glassmorphic Holographic Approval Console (y: 136..235)
        for (int y = 136; y <= 235; y++) {
            uint16_t* rowPtr = &fb[y * 320];
            for (int x = 14; x <= 305; x++) {
                float d_box = sdRoundBox(x - 160.0f, y - 185.5f, 144.0f, 48.5f, 12.0f);
                if (d_box < 0.8f) {
                    int br, bg_, bb;
                    unpackSwap565(rowPtr[x], br, bg_, bb);
                    int gr = (int)(br * 0.16f + 6 * 0.84f);
                    int gg = (int)(bg_ * 0.16f + 18 * 0.84f);
                    int gb = (int)(bb * 0.16f + 34 * 0.84f);
                    if (d_box > -1.4f) {
                        mixRGB(gr, gg, gb, 0, 220, 255, smoothstepf(-1.4f, 0.0f, d_box), gr, gg, gb);
                    }
                    float cov = smoothstepf(0.8f, -0.5f, d_box);
                    mixRGB(br, bg_, bb, gr, gg, gb, cov, br, bg_, bb);
                    rowPtr[x] = packSwap565(br, bg_, bb);
                }

                // Button 1: APPROVE (center 88, 208)
                float d_b1 = sdRoundBox(x - 88.0f, y - 208.0f, 64.0f, 18.5f, 9.0f);
                if (d_b1 < 0.8f) {
                    int br, bg_, bb, c1r, c1g, c1b;
                    unpackSwap565(rowPtr[x], br, bg_, bb);
                    mixRGB(0, 140, 70, 20, 205, 110, clampf((226.0f - y) / 37.0f, 0.0f, 1.0f), c1r, c1g, c1b);
                    if (d_b1 > -1.5f) mixRGB(c1r, c1g, c1b, 120, 255, 195, smoothstepf(-1.5f, 0.0f, d_b1), c1r, c1g, c1b);
                    mixRGB(br, bg_, bb, c1r, c1g, c1b, smoothstepf(0.8f, -0.5f, d_b1), br, bg_, bb);
                    rowPtr[x] = packSwap565(br, bg_, bb);
                }

                // Button 2: DENY (center 232, 208)
                float d_b2 = sdRoundBox(x - 232.0f, y - 208.0f, 64.0f, 18.5f, 9.0f);
                if (d_b2 < 0.8f) {
                    int br, bg_, bb, c2r, c2g, c2b;
                    unpackSwap565(rowPtr[x], br, bg_, bb);
                    mixRGB(165, 25, 35, 230, 65, 70, clampf((226.0f - y) / 37.0f, 0.0f, 1.0f), c2r, c2g, c2b);
                    if (d_b2 > -1.5f) mixRGB(c2r, c2g, c2b, 255, 150, 150, smoothstepf(-1.5f, 0.0f, d_b2), c2r, c2g, c2b);
                    mixRGB(br, bg_, bb, c2r, c2g, c2b, smoothstepf(0.8f, -0.5f, d_b2), br, bg_, bb);
                    rowPtr[x] = packSwap565(br, bg_, bb);
                }
            }
        }

        bool warnPulse = ((now / 400) & 1);
        canvas.fillRoundRect(26, 142, 268, 16, 4, warnPulse ? 0xFA40 : 0xD980);
        canvas.setTextDatum(textdatum_t::middle_center);
        canvas.setTextColor(TFT_WHITE);
        canvas.drawString("PERMISSION REQUIRED", 160, 150, &fonts::Font0);

        canvas.setTextColor(0xFFE0);
        canvas.drawString(approvalPrompt, 160, 173, &fonts::DejaVu18);

        canvas.setTextColor(TFT_WHITE);
        canvas.drawString("APPROVE", 88, 208, &fonts::DejaVu18);
        canvas.drawString("DENY", 232, 208, &fonts::DejaVu18);
    }

    void drawTelemetryTopBar(uint16_t* fb, unsigned long now, int themeIdx) {
        bool pulse = ((now / 600) & 1);
        canvas.fillCircle(17, 10, 3, pulse ? 0x07E0 : 0x0440);
        canvas.setTextDatum(textdatum_t::middle_left);
        canvas.setTextColor(0x859B);
        canvas.drawString("ANTIGRAVITY BOT", 25, 10, &fonts::Font0);

        // Top Right: Quota Telemetry Badge [⚡ GEMINI 93%]
        int badgeW = 76;
        int badgeH = 13;
        int badgeX = 312 - badgeW;
        int badgeY = 4;
        uint16_t badgeCol = (quotaPct >= 70) ? 0x07E0 : ((quotaPct >= 30) ? 0xFDE0 : 0xF900);
        canvas.drawRoundRect(badgeX, badgeY, badgeW, badgeH, 3, badgeCol);
        canvas.setTextDatum(textdatum_t::middle_center);
        canvas.setTextColor(badgeCol);
        canvas.drawString(quotaStr, badgeX + badgeW / 2, badgeY + badgeH / 2 + 1, &fonts::Font0);
        canvas.setTextDatum(textdatum_t::middle_center);
    }

    void drawHoloDashboard(uint16_t* fb, unsigned long now) {
        // 1. Translucent Glassmorphic Backdrop (y: 118..236, x: 14..306)
        // High-performance hybrid: integer fast path for inner core + SDF only for rounded edges
        for (int y = 118; y <= 236; y++) {
            uint16_t* rowPtr = &fb[y * 320];
            bool isBorderY = (y <= 126 || y >= 228);
            for (int x = 14; x <= 306; x++) {
                bool isBorderX = (x <= 24 || x >= 296);
                if (!isBorderX && !isBorderY) {
                    // Fast inner tint (no sqrt / float overhead!)
                    int br, bg_, bb;
                    unpackSwap565(rowPtr[x], br, bg_, bb);
                    int gr = (int)(br * 0.10f + 6 * 0.90f);
                    int gg = (int)(bg_ * 0.10f + 16 * 0.90f);
                    int gb = (int)(bb * 0.10f + 32 * 0.90f);
                    rowPtr[x] = packSwap565(gr, gg, gb);
                } else {
                    float d_box = sdRoundBox(x - 160.0f, y - 177.0f, 144.0f, 57.0f, 10.0f);
                    if (d_box < 0.8f) {
                        int br, bg_, bb;
                        unpackSwap565(rowPtr[x], br, bg_, bb);
                        int gr = (int)(br * 0.10f + 6 * 0.90f);
                        int gg = (int)(bg_ * 0.10f + 16 * 0.90f);
                        int gb = (int)(bb * 0.10f + 32 * 0.90f);
                        if (d_box > -1.5f) {
                            mixRGB(gr, gg, gb, 0, 220, 255, smoothstepf(-1.5f, 0.0f, d_box), gr, gg, gb);
                        }
                        mixRGB(br, bg_, bb, gr, gg, gb, smoothstepf(0.8f, -0.5f, d_box), br, bg_, bb);
                        rowPtr[x] = packSwap565(br, bg_, bb);
                    }
                }
            }
        }

        // 2. Interactive Dual Tab Header (y: 121..138)
        // Tab 0: [ ✦ QUOTA ] (x: 22..154)
        bool tab0Active = (activeHoloTab == 0);
        canvas.fillRoundRect(22, 121, 132, 17, 4, tab0Active ? 0x0359 : 0x0186);
        if (tab0Active) canvas.drawRoundRect(22, 121, 132, 17, 4, 0x07FF);
        canvas.setTextDatum(textdatum_t::middle_center);
        canvas.setTextColor(tab0Active ? TFT_WHITE : 0x8410);
        canvas.drawString("✦ MODEL QUOTA", 88, 129, &fonts::Font0);

        // Tab 1: [ ☀ WEATHER · 杭州 ] (x: 166..298)
        bool tab1Active = (activeHoloTab == 1);
        canvas.fillRoundRect(166, 121, 132, 17, 4, tab1Active ? 0x0359 : 0x0186);
        if (tab1Active) canvas.drawRoundRect(166, 121, 132, 17, 4, 0x07FF);
        canvas.setTextColor(tab1Active ? TFT_WHITE : 0x8410);
        canvas.drawString("☀ WEATHER · 杭州", 232, 129, &fonts::Font0);

        // 3. Tab Body
        if (activeHoloTab == 0) {
            // --- Tab 0: Model Quota ---
            canvas.setTextDatum(textdatum_t::middle_left);
            canvas.setTextColor(0xFFE0);
            canvas.drawString("Gemini", 24, 152, &fonts::DejaVu18);
            canvas.setTextDatum(textdatum_t::middle_right);
            canvas.setTextColor(0x07E0);
            canvas.drawString(quotaGem, 296, 152, &fonts::DejaVu18);
            canvas.drawLine(24, 164, 296, 164, 0x11A7);

            canvas.setTextDatum(textdatum_t::middle_left);
            canvas.setTextColor(0x07FF);
            canvas.drawString("Claude & GPT", 24, 177, &fonts::DejaVu18);
            canvas.setTextDatum(textdatum_t::middle_right);
            canvas.setTextColor(0x07E0);
            canvas.drawString(quotaCla, 296, 177, &fonts::DejaVu18);
            canvas.drawLine(24, 189, 296, 189, 0x11A7);

            canvas.setTextDatum(textdatum_t::middle_left);
            canvas.setTextColor(0xFBE0);
            canvas.drawString("Argon", 24, 202, &fonts::DejaVu18);
            canvas.setTextDatum(textdatum_t::middle_right);
            canvas.setTextColor(0x07E0);
            canvas.drawString(quotaArg, 296, 202, &fonts::DejaVu18);
        } else {
            // --- Tab 1: Weather (Option B) ---
            // Left: 3D Weather Icon at (60, 178)
            if (weatherIcon == 0) {
                // Sunny: Rotating / pulsing sun rays + 3D sun sphere
                for (int i = 0; i < 8; i++) {
                    float ang = i * 0.7854f + now * 0.0015f;
                    float rPulse = 14.0f + 3.0f * sinf(now * 0.007f + i);
                    int rx = 60 + (int)(cosf(ang) * rPulse);
                    int ry = 178 + (int)(sinf(ang) * rPulse);
                    canvas.fillCircle(rx, ry, 2, 0xFFE0);
                }
                canvas.fillCircle(60, 178, 11, 0xFDE0);
                canvas.fillCircle(60, 178, 9, 0xFFE0);
                canvas.fillCircle(57, 175, 4, TFT_WHITE);
            } else if (weatherIcon == 3) {
                // Rain: Cloud + falling rain streaks
                canvas.fillCircle(54, 172, 8, 0x8410);
                canvas.fillCircle(66, 172, 9, 0x9CB2);
                canvas.fillCircle(60, 166, 10, 0xC618);
                for (int i = 0; i < 4; i++) {
                    int rx = 50 + i * 7;
                    int ry = 184 + ((int)(now * 0.04f + i * 7) % 20);
                    canvas.drawLine(rx, ry, rx - 1, ry + 4, 0x07FF);
                }
            } else {
                // Cloudy: Soft 3D Cloud
                canvas.fillCircle(52, 180, 9, 0x8CD2);
                canvas.fillCircle(68, 180, 10, 0x9DF4);
                canvas.fillCircle(60, 172, 12, 0xDEFB);
                canvas.fillCircle(58, 170, 8, TFT_WHITE);
            }

            // Right: Detailed Info Column
            canvas.setTextDatum(textdatum_t::middle_left);
            canvas.setTextColor(TFT_WHITE);
            canvas.drawString(weatherTemp, 106, 152, &fonts::DejaVu24);

            canvas.setTextColor(0xFFE0);
            canvas.drawString(weatherText, 176, 152, &fonts::DejaVu18);

            canvas.setTextColor(0x07FF);
            String rLine = "Today Range: " + String(weatherRange);
            canvas.drawString(rLine.c_str(), 106, 172, &fonts::Font0);

            canvas.setTextColor(0x859B);
            String hLine = "Humidity: " + String(weatherHum);
            canvas.drawString(hLine.c_str(), 106, 187, &fonts::Font0);

            canvas.setTextColor(0x37E6);
            String aLine = "Air Quality: AQI 28 (Good)";
            canvas.drawString(aLine.c_str(), 106, 201, &fonts::Font0);
        }

        // Footer hint
        canvas.setTextDatum(textdatum_t::middle_center);
        canvas.setTextColor(0x8410);
        canvas.drawString("- SWIPE TO FLIP · TAP BOTTOM TO CLOSE -", 160, 226, &fonts::Font0);
    }

    void drawTelemetryAndStatusPill(uint16_t* fb, unsigned long now, int themeIdx) {
        drawTelemetryTopBar(fb, now, themeIdx);

        // Translucent Glassmorphic Bottom Status Pill (y: 214..235)
        int hr = (themeIdx == 2) ? 255 : ((themeIdx == 1) ? 255 : 0);
        int hg = (themeIdx == 2) ? 80  : ((themeIdx == 1) ? 200 : 195);
        int hb = (themeIdx == 2) ? 60  : ((themeIdx == 1) ? 40  : 245);

        for (int y = 213; y <= 236; y++) {
            uint16_t* rowPtr = &fb[y * 320];
            for (int x = 58; x <= 262; x++) {
                float d_pill = sdRoundBox(x - 160.0f, y - 224.5f, 98.0f, 10.5f, 10.0f);
                if (d_pill < 0.8f) {
                    int br, bg_, bb;
                    unpackSwap565(rowPtr[x], br, bg_, bb);
                    int pr = (int)(br * 0.20f + 6 * 0.80f);
                    int pg = (int)(bg_ * 0.20f + 20 * 0.80f);
                    int pb = (int)(bb * 0.20f + 38 * 0.80f);
                    if (d_pill > -1.2f) {
                        mixRGB(pr, pg, pb, hr, hg, hb, smoothstepf(-1.2f, 0.0f, d_pill) * 0.60f, pr, pg, pb);
                    }
                    mixRGB(br, bg_, bb, pr, pg, pb, smoothstepf(0.8f, -0.5f, d_pill), br, bg_, bb);
                    rowPtr[x] = packSwap565(br, bg_, bb);
                }
            }
        }

        canvas.setTextColor(0xE79F);
        canvas.drawString(statusText, 160, 224, &fonts::DejaVu18);
    }
};
