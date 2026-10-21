// vs-mod: hooks do Ragnarok Survivors no Vampire Survivors 1.15.113 (update v0.27.0, Unity 6000.0.62f1).
// Grava em sd:/vs-mod/probe.log. Offsets = RVA do Il2CppDumper (~/vs-decomp/dump/dump.cs).
// Logger e padrão de hook herdados do drova-switch-mod/exl.
#include "lib.hpp"
#include "nn/fs.hpp"
#include <atomic>
#include <cstdio>
#include <cstring>

namespace {

constexpr u64 kTicksPerMs = 19200;  // contador do sistema: 19,2 MHz
u64 g_t0;

// ponytail: buffer estático + spinlock, flush a cada linha depois que o nn::fs existe
char g_buf[32 * 1024];
size_t g_len;
std::atomic_flag g_lock = ATOMIC_FLAG_INIT;
bool g_mounted;
bool g_fsReady;  // nn::fs no exl_main derruba o jogo (PC=0 em CreateDirectory); liga no 1º hook de gameplay
s64 g_filePos;

constexpr const char* kDir = "vsprobe:/vs-mod";
constexpr const char* kPath = "vsprobe:/vs-mod/probe.log";

void FlushLocked() {
    if (g_len == 0) return;
    if (!g_mounted) {
        if (R_FAILED(nn::fs::MountSdCardForDebug("vsprobe"))) return;
        nn::fs::CreateDirectory(kDir);
        nn::fs::CreateFile(kPath, 0);
        g_mounted = true;
    }
    nn::fs::FileHandle h;
    if (R_FAILED(nn::fs::OpenFile(&h, kPath, nn::fs::OpenMode_Write | nn::fs::OpenMode_Append))) return;
    if (g_filePos == 0) nn::fs::GetFileSize(&g_filePos, h);
    nn::fs::WriteFile(h, g_filePos, g_buf, g_len, nn::fs::WriteOption::CreateOption(nn::fs::WriteOptionFlag_Flush));
    g_filePos += g_len;
    nn::fs::CloseFile(h);
    g_len = 0;
}

template <typename... Args>
void Log(const char* fmt, Args... args) {
    char line[256];
    u64 ms = (svcGetSystemTick() - g_t0) / kTicksPerMs;
    int n = std::snprintf(line, sizeof(line), "%8lu.%03lu ", ms / 1000, ms % 1000);
    n += std::snprintf(line + n, sizeof(line) - n, fmt, args...);
    if (n > (int)sizeof(line) - 2) n = sizeof(line) - 2;
    line[n++] = '\n';
    while (g_lock.test_and_set(std::memory_order_acquire)) {}
    if (g_len + n <= sizeof(g_buf)) { std::memcpy(g_buf + g_len, line, n); g_len += n; }
    if (g_fsReady) FlushLocked();
    g_lock.clear(std::memory_order_release);
}

template <typename T> T& Fld(void* o, int off) { return *reinterpret_cast<T*>((char*)o + off); }

}  // namespace

template <typename R, typename... A> R Call(uintptr_t rva, A... a) {
    return reinterpret_cast<R (*)(A..., void*)>(exl::util::modules::GetTargetOffset(rva))(a..., nullptr);
}
struct V3 { float x, y, z; };  // Vector3 por valor = HFA em s0..s2
struct V2 { float x, y; };

// string gerenciada a partir de ASCII: Marshal.PtrToStringUni(IntPtr) com UTF-16 montado na pilha
void* NewString(const char* ascii) {
    char16_t w[64];
    size_t i = 0;
    for (; ascii[i] && i < 63; i++) w[i] = ascii[i];
    w[i] = 0;
    return Call<void*>(0x99D3920, (const void*)w);
}

// Densidade da arte do personagem: o atlas é N× (RO nativo) e o VS desenha pelo nº de pixels, então o jogador
// encolhe 1/N (ver InitCharacter).
#ifndef PLAYER_ART_SCALE
#define PLAYER_ART_SCALE (1.f / 3.f)
#endif
constexpr float kPlayerArtScale = PLAYER_ART_SCALE;  // -DPLAYER_ART_SCALE=1 = controle vanilla
void* g_player;
u64 g_initTick;  // InitCharacter do jogador (tempo de run no log de dano)

// Andar em 8 direções: tools/reskin_char.py põe no atlas "<skin>_d{0..7}_{01..}" (direção do RO: 0 = sul, sentido
// horário, 6 = leste). Registra walk_d0..7 no SpriteAnimation do jogador; PlayWalkingAnimations escolhe pela direção.
// Qualquer personagem: o prefixo sai do spriteName do CharacterData ("newImelda_01.png" -> "newImelda_"); quem não
// tem os sprites _d0_01.. no atlas (personagem ainda com arte do VS) fica de fora e sem a escala 1/N.
bool SkinPrefix(void* str, char* out, int cap) {
    if (!str) return false;
    int n = Fld<int>(str, 0x10);
    const char16_t* c = reinterpret_cast<const char16_t*>((char*)str + 0x14);
    if (n < 7 || n - 6 >= cap) return false;
    for (int i = 0; i < n - 6; i++) out[i] = (char)c[i];  // tira "01.png"
    out[n - 6] = 0;
    return true;
}
constexpr int kDirFrames = 8, kDirFps = 16;     // 8 quadros do RO no mesmo ciclo do andar do VS (4 quadros a 8 fps)
bool g_has8;
int g_dir = -1;

void SetupDirections(void* self) {
    g_has8 = false; g_dir = -1;
    void* cd = Fld<void*>(self, 0x118);  // CharacterData (SetupAnimation: textureName +0x40, spriteName +0x48)
    void* anim = Fld<void*>(self, 0xD0);
    char skin[48];
    if (!cd || !anim || !SkinPrefix(Fld<void*>(cd, 0x48), skin, sizeof skin)) return;
    for (int d = 0; d < 8; d++) {
        char pre[64], name[16];
        std::snprintf(pre, sizeof pre, "%sd%d_", skin, d);
        std::snprintf(name, sizeof name, "walk_d%d", d);
        // SpriteManager.GetAnimationFrames(prefix, 1, n, pivot (0.5, 0), textureName, zeroPad 2, false), como o jogo
        void* list = Call<void*>(0xCEFA5F0, NewString(pre), 1, kDirFrames, V2{0.5f, 0.f}, Fld<void*>(cd, 0x40), 2, false);
        int n = list ? Fld<int>(list, 0x18) : -1;  // List<T>._size; _items +0x10, elementos do array em +0x20
        for (int i = 0; i < n; i++) if (!Fld<void*>(Fld<void*>(list, 0x10), 0x20 + 8 * i)) n = -2;  // sprite faltando
        if (n != kDirFrames) { Log("  8dir: %s -> %d quadros, sem arte RO", pre, n); return; }
        // AddAnimation(name, frames, fps, loop, startRandomFrame, onComplete, autoSetAnimation=false)
        Call<void>(0xCEF4770, anim, NewString(name), list, kDirFps, true, false, (void*)nullptr, false);
    }
    Fld<u8>(self, 0x241) = 0;  // _canFlip: a direção vem do quadro, não do espelho
    // os sprites originais do personagem ficaram em 1× pra UI (card do menu); no jogo começa já no andar RO, leste
    Call<void>(0xCEF56D0, anim, NewString("walk_d6"));  // BaseSpriteAnimation.SetAnimation(string)
    g_dir = 6;
    g_has8 = true;
    Log("  8dir: walk_d0..7 registrados");
}

// CharacterController.PlayWalkingAnimations (todo frame, de InternalUpdate): o original põe "walk" quando o
// _currentAnimation (+0xF8) vira 10; depois dele, troca pra walk_dN quando a direção muda ou o "walk" voltou.
HOOK_DEFINE_TRAMPOLINE(PlayWalking) {
    static void Callback(void* self, void* m) {
        int before = Fld<int>(self, 0xF8);
        Orig(self, m);
        if (self != g_player || !g_has8) return;
        V2 v = Fld<V2>(self, 0x170);  // _currentDirection
        if (v.x * v.x + v.y * v.y < 1e-6f) return;  // parado: o jogo pausa no quadro atual
        // _isFlipped (+0x242): com _canFlip=0 o InternalUpdate não atualiza, e o chicote (e quem mira pelo lado)
        // lê ele; mesma regra do VS (x<0 = esquerda), vertical puro mantém o lado
        if (v.x < -1e-3f || v.x > 1e-3f) {
            u8 f = v.x < 0;
            Fld<u8>(self, 0x242) = f;
        }
        int k = (int)__builtin_lroundf(__builtin_atan2f(v.y, v.x) / 0.78539816f);
        int dir = ((6 - k) % 8 + 8) % 8;  // ângulo 0 = leste = 6; anti-horário no Unity = horário no RO
        if (dir == g_dir && !(before != 10 && Fld<int>(self, 0xF8) == 10)) return;
        g_dir = dir;
        Fld<u8>(self, 0x241) = 0;
        char name[16];
        std::snprintf(name, sizeof name, "walk_d%d", dir);
        Call<void>(0xCEF56D0, Fld<void*>(self, 0xD0), NewString(name));  // BaseSpriteAnimation.SetAnimation(string)
    }
};

// Sprites de alta densidade: o VS mede todo sprite pelo rect em pixels (Phaser: tamanho = pixels × scale, PPU fixo
// em 100), no mundo e na UI. Atlas reescritos com d× pixels marcam os sprites com PPU = 100·d + 1; pro código do
// jogo, rect e pivô voltam ao tamanho do VS (o desenho nativo do Unity usa os dados do sprite e fica com o detalhe).
// O jogador (PPU 100·N redondo) segue pela escala na raiz.
struct Rect4 { float x, y, w, h; };
static float HiDensity(void* sprite) {
    float ppu = Call<float>(0xB2BD990, sprite);  // Sprite.get_pixelsPerUnit
    int ip = (int)(ppu + 0.5f);
    return (ip > 100 && ip % 100 == 1) ? (float)(ip / 100) : 1.f;
}
HOOK_DEFINE_TRAMPOLINE(SpriteRect) {
    static Rect4 Callback(void* self, void* m) {
        Rect4 r = Orig(self, m);
        float d = HiDensity(self);
        if (d != 1.f) { r.x /= d; r.y /= d; r.w /= d; r.h /= d; }
        return r;
    }
};
HOOK_DEFINE_TRAMPOLINE(SpritePivot) {
    static V2 Callback(void* self, void* m) {
        V2 v = Orig(self, m);
        float d = HiDensity(self);
        if (d != 1.f) { v.x /= d; v.y /= d; }
        return v;
    }
};

// LaurelWeapon.InternalUpdate: o anel do escudo (_Renderer +0x158, sprite Shockwave2; o InitWeapon grava localScale
// 1,25) é filho da raiz do jogador, que o InitCharacter escala por kPlayerArtScale — sem compensar, o anel fica do
// tamanho dos pés (playtest do Zero, 16/10). A arma inicial nasce dentro do InitCharacter, antes da raiz escalar,
// por isso a correção é por frame. Laurel e Crimson Shroud usam a mesma classe.
constexpr float kShieldWorld = 2.0f;
HOOK_DEFINE_TRAMPOLINE(LaurelUpdate) {
    static void Callback(void* self, void* m) {
        Orig(self, m);
        if (!g_player || kPlayerArtScale == 1.f) return;
        void* r = Fld<void*>(self, 0x158);
        void* rt = r ? Call<void*>(0xB387D00, r) : nullptr;  // Component.get_transform
        void* root = Call<void*>(0xCF60770, g_player);        // get_CachedTransform
        if (!rt || !root || !Call<bool>(0xB3B9620, rt, root)) return;  // IsChildOf
        // 2,0 no mundo (o VS usa 1,25 pro Antonio): o jogador RO em 0,65 é mais alto e o anel ficava nos pés dele
        // (Zero, 16/10: "o escudo também está pequeno ainda")
        float k = kShieldWorld / Call<V3>(0xB3B3830, root).x;  // Transform.get_localScale
        Call<void>(0xB3B3970, rt, V3{k, k, 1.25f});
    }
};

// Efeitos do RO animados (tools/rofx.py): Projectile.OnUpdate é a base que só 16 das 414 subclasses sobrescrevem;
// depois dele, se a classe do projétil está na tabela, o SpriteRenderer do campo indicado (_renderer +0x80, ou outro
// como o _GroundFx +0xD0 do Nduja) recebe o quadro rofx_<classe>_NN da hora. Chave pela classe, não pelo sprite:
// Rings3 é o anel do Garlic, do Pentagram, do Clock Lancet e do Vortex. Estado por renderer (o pool reaproveita o
// projétil): sem update há >200 ms = projétil novo, a animação recomeça.
// fld2 = campo dentro de fld (0 = o próprio fld); alpha 0 = a do VS; hide = campo+campo até um SpriteRenderer do VS que some (o raio rolante do Lightning Ring)
struct RoFx { const char* cls; const char* pre; int n, fps; bool loop; int fld, fld2; float alpha; int hide0, hide1; };
struct C4 { float r, g, b, a; };
const RoFx kRoFx[] = {
#include "rofx_table.inc"
};
constexpr int kNFx = sizeof(kRoFx) / sizeof(kRoFx[0]);
void* g_fxFrame[kNFx][48];  // = MAXF em tools/rofx.py
s8 g_fxState[kNFx];  // 0 = não carregado, 1 = ok, -1 = faltou quadro (efeito desligado)

bool FxReady(int fx) {
    if (g_fxState[fx] == 0) {
        g_fxState[fx] = kRoFx[fx].n <= 48 ? 1 : -1;
        for (int i = 0; i < kRoFx[fx].n && i < 48; i++) {
            char name[64];
            std::snprintf(name, sizeof name, "%s%02d", kRoFx[fx].pre, i + 1);
            if (!(g_fxFrame[fx][i] = Call<void*>(0xCEF7970, NewString(name), true))) g_fxState[fx] = -1;  // GetSprite
        }
        Log("rofx %s: %s", kRoFx[fx].cls, g_fxState[fx] > 0 ? "ok" : "sem quadros");
    }
    return g_fxState[fx] > 0;
}
// classe IL2CPP (objeto +0 = Il2CppClass*, nome em +0x10) → efeito (-1 = nenhum)
struct ClsFx { void* k; int fx; };
ClsFx g_clsFx[512];
int FxOf(void* obj) {
    void* k = Fld<void*>(obj, 0);
    u32 h = (u32)((uintptr_t)k >> 4) & 511;
    for (int i = 0; i < 512; i++, h = (h + 1) & 511) {
        ClsFx& e = g_clsFx[h];
        if (e.k == k) return e.fx;
        if (e.k) continue;
        const char* name = Fld<const char*>(k, 0x10);
        e = {k, -1};
        for (int j = 0; j < kNFx; j++) if (!std::strcmp(name, kRoFx[j].cls)) e.fx = j;
        if (e.fx >= 0 && !FxReady(e.fx)) e.fx = -1;
        return e.fx;
    }
    return -1;
}
struct RendFx { void* r; u64 t0, last; };
RendFx g_rendFx[1024];
void PlayFx(void* self) {
    if (kNFx == 0) return;
    int fx = FxOf(self);
    if (fx < 0) return;
    const RoFx& f = kRoFx[fx];
    void* r = Fld<void*>(self, f.fld);
    if (r && f.fld2) r = Fld<void*>(r, f.fld2);  // ex.: _groundFx (PhaserSprite) → _spriteRenderer +0x28
    if (!r) return;
    u64 now = svcGetSystemTick(), stale = 200 * kTicksPerMs;
    u32 h = (u32)((uintptr_t)r >> 4) & 1023;
    RendFx* e = nullptr;
    for (int k = 0; k < 1024 && !e; k++, h = (h + 1) & 1023)
        if (g_rendFx[h].r == r || !g_rendFx[h].r || now - g_rendFx[h].last > 10 * stale) e = &g_rendFx[h];
    if (!e) return;
    if (e->r != r || now - e->last > stale) *e = {r, now, now};
    e->last = now;
    static bool shown[kNFx > 0 ? kNFx : 1];
    if (!shown[fx]) {  // uma linha por efeito: confirma no probe.log que o hook achou o renderer
        shown[fx] = true;
        V3 ls = Call<V3>(0xB3B94E0, Call<void*>(0xB387D00, r));  // Transform.get_lossyScale
        Log("rofx %s: 1º quadro, escala no mundo (%.2f %.2f), enabled %d, alfa %.2f", f.cls, ls.x, ls.y,
            (int)Call<bool>(0xB2FEFA0, r), Call<C4>(0xB2BAC10, r).a);  // Renderer.get_enabled, SpriteRenderer.get_color
        Log("  objeto ativo %d (na hierarquia %d)", (int)Call<bool>(0xB392930, Call<void*>(0xB387F00, r)),
            (int)Call<bool>(0xB392A50, Call<void*>(0xB387F00, r)));
    }
    if (f.hide0) {
        void* h0 = Fld<void*>(self, f.hide0);
        void* hr = h0 && f.hide1 ? Fld<void*>(h0, f.hide1) : h0;
        if (hr) Call<void>(0xB2FF0C0, hr, false);  // Renderer.set_enabled
        Call<void>(0xB2FF0C0, r, true);  // o renderer do RO assume no lugar (o "Sprite" do raio nasce desligado)
        void* go = Call<void*>(0xB387F00, r);  // Component.get_gameObject
        if (go && !Call<bool>(0xB392930, go)) Call<void>(0xB3927F0, go, true);  // activeSelf / SetActive
    }
    u64 i = (now - e->t0) * f.fps / (1000 * kTicksPerMs);
    i = f.loop ? i % f.n : (i < (u64)f.n ? i : f.n - 1);
    Call<void>(0xB2BA130, r, g_fxFrame[fx][i]);  // SpriteRenderer.set_sprite
    if (f.alpha > 0) {  // o VS desenha o anel do Garlic com alfa 0,1-0,2: o quadro do RO some
        C4 c = Call<C4>(0xB2BAC10, r);  // SpriteRenderer.get_color / set_color
        c.a = f.alpha;
        Call<void>(0xB2BAD50, r, c);
    }
}
HOOK_DEFINE_TRAMPOLINE(ProjectileFx) {
    static void Callback(void* self, void* m) { Orig(self, m); PlayFx(self); }
};
// armas que desenham o próprio efeito (o anel do Garlic é o _Renderer +0x158 da arma, não do projétil)
HOOK_DEFINE_TRAMPOLINE(GarlicFx) {
    static void Callback(void* self, void* m) { Orig(self, m); PlayFx(self); }
};

// CharacterController.InitCharacter(CharacterType, int playerIndex, bool asRemote, bool dontGetCharacterData)
// Escala na raiz (como o _scaleMul dos inimigos): a ArcadeTransform calcula displayOrigin e o offset do body pelo
// tamanho do quadro em pixels; escalar só o renderer deixava o hitbox ~20 px à esquerda e ~40 px acima do desenho
// (gemas rodando em volta sem serem pegas). Com a raiz em 1/N, todo o local fica N× e o círculo é refeito N× maior
// (raio e offset), o que devolve no mundo o hitbox vanilla.
u64 NullF(float v) { u32 b; std::memcpy(&b, &v, 4); return (u64)b << 32 | 1; }  // Nullable<float> em registrador

HOOK_DEFINE_TRAMPOLINE(InitCharacter) {
    static void Callback(void* self, int type, int player, bool remote, bool dontGet, void* m) {
        g_fsReady = true;
        Orig(self, type, player, remote, dontGet, m);
        g_player = self;
        g_initTick = svcGetSystemTick();
        SetupDirections(self);
        if (kPlayerArtScale != 1.f && g_has8) {
            void* tr = Call<void*>(0xCF60770, self);  // get_CachedTransform
            void* body = Fld<void*>(self, 0x28);
            if (tr && body) {
                float r = Fld<float>(body, 0x44), ox = Fld<float>(body, 0x48), oy = Fld<float>(body, 0x4C);
                Call<void>(0xB3B3970, tr, V3{kPlayerArtScale, kPlayerArtScale, 1.f});  // Transform.set_localScale
                // setCircle(px, offX px, offY px, worldSpace=false): guarda px×0,01 e offset.y = -offY
                float k = 100.f / kPlayerArtScale;
                Call<void*>(0x9DC9BD0, body, r * k, NullF(ox * k), NullF(-oy * k), false);
                // Body.updateBounds refaz _size = _sourceSize (+0xE0) × escala a cada frame; o setCircle não mexe nele
                Fld<V2>(body, 0xE0) = Fld<V2>(body, 0x58);
                Log("  raiz x%.3f; circle r %.4f -> %.4f local, world %.4f", kPlayerArtScale, r, Fld<float>(body, 0x44),
                    Call<float>(0x9DCA040, body));
            }
            // filhos da raiz com deslocamento local (ímã +0x248, barra de vida +0xE8): o deslocamento encolheria junto
            // (medido: ímã ~6 px abaixo, barra ~2 px acima do vanilla)
            for (int off : {0x248, 0xE8}) {
                void* c = Fld<void*>(self, off);
                void* ct = c ? Call<void*>(0xB387D00, c) : nullptr;
                if (!ct) continue;
                V3 lp = Call<V3>(0xB3B1B40, ct);  // Transform.get/set_localPosition
                Call<void>(0xB3B1C80, ct, V3{lp.x / kPlayerArtScale, lp.y / kPlayerArtScale, lp.z});
            }
            // a barra de vida é filha da raiz e encolheria junto (get/set_HealthBarScale)
            float hb = Call<float>(0xCF5FB90, self);
            Call<void>(0xCF5FCF0, self, hb / kPlayerArtScale);
            Log("  healthBarScale %.3f -> %.3f", hb, Call<float>(0xCF5FB90, self));
        }
        Log("InitCharacter type=%d player=%d scale=%.3f", type, player, kPlayerArtScale);
    }
};

// CharacterController.InternalUpdate: mede o raio de colisão do jogador ~3 s depois do início
HOOK_DEFINE_TRAMPOLINE(PlayerUpdate) {
    static void Callback(void* self, void* m) {
        Orig(self, m);
        static int frames;
        if (self != g_player || (++frames != 180 && frames != 900)) return;
        void* body = Fld<void*>(self, 0x28);
        if (!body) return;
        Log("player world=%.4f phaser=%.4f", Call<float>(0x9DCA040, body), Call<float>(0x9DCA020, body));
        // BaseBody: _offset +0x48, _position +0x50, _size +0x58, _center +0x68; ArcadeTransform (+0x28 do body):
        // position +0x48, scale +0x50, displayOrigin +0x6C, _origin +0x74
        V2 off = Fld<V2>(body, 0x48), pos = Fld<V2>(body, 0x50), sz = Fld<V2>(body, 0x58), c = Fld<V2>(body, 0x68);
        Log("  body off=(%.3f,%.3f) pos=(%.3f,%.3f) size=(%.3f,%.3f) center=(%.3f,%.3f) circle=%d", off.x, off.y,
            pos.x, pos.y, sz.x, sz.y, c.x, c.y, Fld<u8>(body, 0x41));
        void* mz = Fld<void*>(self, 0x248);  // MagnetZone (ArcadeSprite; body em +0x28 como o jogador)
        void* mb = mz ? Fld<void*>(mz, 0x28) : nullptr;
        if (mb) {
            V2 mp = Fld<V2>(mb, 0x50), ms = Fld<V2>(mb, 0x58), mc = Fld<V2>(mb, 0x68);
            Log("  magnet world=%.4f _radius=%.4f pos=(%.3f,%.3f) size=(%.3f,%.3f) center=(%.3f,%.3f)",
                Call<float>(0x9DCA040, mb), Fld<float>(mb, 0x44), mp.x, mp.y, ms.x, ms.y, mc.x, mc.y);
        }
        void* hb = Fld<void*>(self, 0xE8);  // HealthBar
        if (hb) {
            V3 hp = Call<V3>(0xB3B1880, Call<void*>(0xB387D00, hb)), rp = Call<V3>(0xB3B1880, Call<void*>(0xCF60770, self));
            Log("  healthbar - raiz = (%.3f,%.3f)", hp.x - rp.x, hp.y - rp.y);  // Transform.get_position
        }
        void* at = Fld<void*>(body, 0x28);
        if (at) {
            V2 tp = Fld<V2>(at, 0x48), ts = Fld<V2>(at, 0x50), dor = Fld<V2>(at, 0x6C), org = Fld<V2>(at, 0x74);
            Log("  arcade pos=(%.3f,%.3f) scale=(%.2f,%.2f) displayOrigin=(%.3f,%.3f) origin=(%.2f,%.2f)", tp.x, tp.y,
                ts.x, ts.y, dor.x, dor.y, org.x, org.y);
        }
    }
};

int g_enemyType = -1;
int g_lastType = -1;  // ponytail: tipo do último InitEnemy; serve pro 1º inimigo de cada tipo (o probe só mede um)  // >= 0 enquanto um InitEnemy roda (filtra os setCircle de arma/projétil)
int g_circleLogs;

// BaseBody.setCircle(float radius, float? offsetX, float? offsetY, bool worldSpace): Nullable<float> vem empacotado
// em 8 bytes (hasValue no byte baixo, valor nos 32 de cima), como o SetBodyRadius monta
HOOK_DEFINE_TRAMPOLINE(SetCircle) {
    static void* Callback(void* self, float radius, u64 ox, u64 oy, bool world, void* m) {
        void* r = Orig(self, radius, ox, oy, world, m);
        if (g_player && self == Fld<void*>(g_player, 0x28))
            Log("  setCircle PLAYER arg=%.4f world=%d -> _radius=%.4f", radius, world, Fld<float>(self, 0x44));
        else if (g_enemyType >= 0 && g_circleLogs++ < 60)
            Log("  setCircle enemy=%d arg=%.4f world=%d -> _radius=%.4f", g_enemyType, radius, world, Fld<float>(self, 0x44));
        return r;
    }
};

// EnemyController.SetBodyRadius(float): quem chama com qual raio
HOOK_DEFINE_TRAMPOLINE(SetBodyRadius) {
    static void Callback(void* self, float radius, void* m) {
        if (g_circleLogs < 60) Log("  SetBodyRadius enemy=%d radius=%.4f", g_enemyType, radius);
        Orig(self, radius, m);
    }
};

// EnemyController.InitEnemy(EnemyType, bool asRemote): mede o hitbox (body._radius) e o _scaleMul do ENEMY_DATA
HOOK_DEFINE_TRAMPOLINE(InitEnemy) {
    static void Callback(void* self, int type, bool remote, void* m) {
        g_enemyType = type;
        Orig(self, type, remote, m);
        g_enemyType = -1;
        g_lastType = type;
        static int seen[512];
        if (type >= 0 && type < 512 && seen[type]++ == 0) {
            void* body = Fld<void*>(self, 0x28);  // PhaserGameObject.body
            float r = body ? Fld<float>(body, 0x44) : -1.f;  // BaseBody._radius
            Log("InitEnemy type=%d scaleMul=%.3f radius=%.4f", type, Fld<float>(self, 0x1B8), r);
        }
    }
};

// PixelPerfectCamera (URP 2D) em UpscaleRenderTexture desenha o mundo na resolução de referência e amplia: nada
// abaixo de 1 pixel do VS aparece. HIRES força GridSnapping=None (render na resolução da tela).
HOOK_DEFINE_TRAMPOLINE(PpcUpdate) {
    static void Callback(void* self, void* m) {
        static bool logged;
        if (!logged) {
            logged = true;
            Log("PixelPerfectCamera ppu=%d ref=%dx%d crop=%d grid=%d filter=%d", Fld<int>(self, 0x20), Fld<int>(self, 0x24),
                Fld<int>(self, 0x28), Fld<int>(self, 0x2C), Fld<int>(self, 0x30), Fld<int>(self, 0x34));
        }
#ifdef HIRES
        Fld<int>(self, 0x30) = 0;  // GridSnapping.None
#endif
        Orig(self, m);
    }
};

// UniversalRenderPipelineAsset.get_renderScale: < 1 desenha o mundo menor e amplia (a UI overlay fica nítida)
HOOK_DEFINE_TRAMPOLINE(RenderScale) {
    static float Callback(void* self, void* m) {
        float v = Orig(self, m);
        static bool logged;
        if (!logged) { logged = true; Log("URP renderScale=%.3f", v); }
#ifdef HIRES
        return 1.f;
#else
        return v;
#endif
    }
};

// CameraExtensions.GetRenderTextureSize(Camera) -> int2: o VS desenha o mundo num RenderTexture desse tamanho
// (RenderTextureResizer.UpdateRT) e mostra ampliado numa RawImage — por isso a UI é nítida e o mundo não.
// HIRES: RT até 3× maior (limitado a 1080 linhas, a saída docked do Switch); a câmera não muda, só ganha pixels.
struct Int2 { int x, y; };
int g_rtFactor = 1;  // quanto o RT do mundo foi ampliado (a câmera precisa saber, senão afasta o zoom)
HOOK_DEFINE_TRAMPOLINE(RtSize) {
    static Int2 Callback(void* camera, void* m) {
        Int2 r = Orig(camera, m);
        Int2 o = r;
#ifdef HIRES
        int f = 3;
        while (f > 1 && r.y * f > 1080) f--;
        r.x *= f; r.y *= f;
        g_rtFactor = f;
#endif
        static int lastY;
        if (o.y != lastY) { lastY = o.y; Log("RT %dx%d -> %dx%d", o.x, o.y, r.x, r.y); }
        return r;
    }
};

// ProCamera2DPixelPerfect.ResizeCameraToPixelPerfect: o tamanho ortográfico sai de PixelsPerUnit (+0x60) e do RT;
// com o RT f× maior a câmera mostraria f× mais mapa. PixelsPerUnit × f só durante o cálculo mantém o enquadramento.
HOOK_DEFINE_TRAMPOLINE(PpResize) {
    static void Callback(void* self, void* m) {
        float& ppu = Fld<float>(self, 0x60);
        float orig = ppu;
        ppu = orig * g_rtFactor;
        Orig(self, m);
        ppu = orig;
        static int logged;
        if (logged++ < 3) Log("ppResize ppu=%.1f x%d", orig, g_rtFactor);
    }
};

// EnemyController.OnUpdate: ~3 s depois do spawn (tween de escala acabou) mede o raio que a colisão usa
HOOK_DEFINE_TRAMPOLINE(EnemyOnUpdate) {
    static void Callback(void* self, void* m) {
        Orig(self, m);
        static void* first[512]; static int frames[512];
        int type = g_lastType;
        if (type < 0 || type >= 512) return;
        if (!first[type]) first[type] = self;
        if (first[type] != self || ++frames[type] != 180) return;
        void* body = Fld<void*>(self, 0x28);
        if (!body) return;
        Log("radius type=%d scaleMul=%.3f world=%.4f phaser=%.4f _radius=%.4f", type, Fld<float>(self, 0x1B8),
            Call<float>(0x9DCA040, body), Call<float>(0x9DCA020, body), Fld<float>(body, 0x44));
    }
};

// CharacterController.GetDamaged(float): dano no jogador (compara dificuldade entre arte vanilla e RO)
HOOK_DEFINE_TRAMPOLINE(PlayerDamaged) {
    static bool Callback(void* self, float dmg, void* m) {
#ifdef GODMODE
        if (self == g_player) return false;  // só bancada (build 8dg): observar a run sem morrer; nunca no pacote
#endif
        bool r = Orig(self, dmg, m);
        static int hits; static float total;
        if (self == g_player && r) {
            ++hits; total += dmg;
            float t = (svcGetSystemTick() - g_initTick) / (kTicksPerMs * 1000.f);
            if (hits <= 5 || hits % 20 == 0 || Fld<float>(self, 0x228) <= 0)
                Log("hit #%d t=%.1fs dmg=%.1f total=%.1f hp=%.1f", hits, t, dmg, total, Fld<float>(self, 0x228));
        }
        return r;
    }
};

// Pickup.GetTaken: conta gemas/itens pegos (a gema que roda em volta sem ser pega não chega aqui)
int g_taken;
HOOK_DEFINE_TRAMPOLINE(PickupTaken) {
    static void Callback(void* self, void* m) {
        Orig(self, m);
        if (++g_taken <= 3 || g_taken % 50 == 0) Log("pickup taken #%d", g_taken);
    }
};

extern "C" void exl_main(void* x0, void* x1) {
    g_t0 = svcGetSystemTick();
    exl::hook::Initialize();
    InitCharacter::InstallAtOffset(0xCF67B50);
    LaurelUpdate::InstallAtOffset(0xCECA6F0);  // LaurelWeapon.InternalUpdate
    SpriteRect::InstallAtOffset(0xB2BCF50);   // Sprite.get_rect
    SpritePivot::InstallAtOffset(0xB2BDDD0);  // Sprite.get_pivot
    InitEnemy::InstallAtOffset(0xD06F530);
    SetCircle::InstallAtOffset(0x9DC9BD0);
    SetBodyRadius::InstallAtOffset(0xD07A450);
    EnemyOnUpdate::InstallAtOffset(0xD0708B0);
    PlayerUpdate::InstallAtOffset(0xCF780A0);
    PpcUpdate::InstallAtOffset(0xAFD3A20);  // PixelPerfectCamera.UpdateCameraProperties
    RenderScale::InstallAtOffset(0xB0105D0);
    RtSize::InstallAtOffset(0xCEDF770);
    PpResize::InstallAtOffset(0x9F9BF90);
    PlayWalking::InstallAtOffset(0xCF78740);
    PickupTaken::InstallAtOffset(0xCC76380);
    PlayerDamaged::InstallAtOffset(0xCF73330);
    ProjectileFx::InstallAtOffset(0xCC0FB60);  // Projectile.OnUpdate
    GarlicFx::InstallAtOffset(0xCEA8310);      // GarlicWeapon.InternalUpdate
    Log("vs-mod vivo");
}

extern "C" NORETURN void exl_exception_entry() {
    EXL_ABORT("Default exception handler called!");
}
