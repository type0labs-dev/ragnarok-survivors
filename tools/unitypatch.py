#!/usr/bin/env python3
# Patch cirúrgico de arquivos Unity 6 (SerializedFile v22) sem re-serializar.
# Por quê: o save do UnityPy 1.25 não faz round-trip no v22 — todo arquivo muda mesmo sem edição e o jogo fecha no
# boot (ExitProcess). Aqui os arquivos internos vão byte a byte; objeto alterado é anexado no fim do arquivo e só a
# entrada dele na tabela de objetos (path_id, byte_start i64, byte_size u32) é reapontada.
import struct
import UnityPy
from UnityPy.files import SerializedFile
from UnityPy.streams import EndianBinaryReader


class Bundle:
    def __init__(self, path):
        self.env = UnityPy.load(path)
        self.bundle = self.env.file
        self.raw = {n: bytearray(f.reader.bytes if isinstance(f, SerializedFile) else f.bytes)
                    for n, f in self.bundle.files.items()}

    def serialized(self):
        return [(n, f) for n, f in self.bundle.files.items() if isinstance(f, SerializedFile)]

    def replace_object(self, file_name, obj, data: bytes):
        """Troca os bytes do objeto: no lugar se couber igual, senão anexa no fim e reaponta a tabela."""
        f = self.bundle.files[file_name]
        raw = self.raw[file_name]
        h = f.header
        assert h.version == 22 and f.reader.endian == "<", "só testado em v22 little-endian"
        start = obj.byte_start  # UnityPy já soma o data_offset; na tabela fica relativo
        if len(data) == obj.byte_size:
            raw[start:start + len(data)] = data
            return
        key = struct.pack("<qqI", obj.path_id, obj.byte_start - h.data_offset, obj.byte_size)
        meta = bytes(raw[:h.data_offset])
        pos = meta.find(key)
        assert pos > 0 and meta.find(key, pos + 1) < 0, f"entrada do objeto {obj.path_id} não é única na tabela"
        raw.extend(b"\0" * ((-len(raw)) % 16))
        new_start = len(raw) - h.data_offset
        raw.extend(data)
        raw[pos:pos + 20] = struct.pack("<qqI", obj.path_id, new_start, len(data))
        raw[0x18:0x20] = struct.pack(">q", len(raw))  # file_size do header v22 (big-endian)

    def add_objects(self, file_name, new):
        """Acrescenta objetos: new = [(path_id, type_id, bytes)], type_id = índice em f.types. Chamar depois de
        todos os replace_object (eles usam o data_offset original). Layout v22 verificado nos bytes: contagem i32
        alinhada a 4 a partir de 0x30, entradas de 24 B (path_id, byte_start rel., size, type_id) ordenadas por
        path_id; depois da tabela vêm scripts/externals/refs/userinfo; data_offset = align16(fim do metadata)."""
        f = self.bundle.files[file_name]
        raw = self.raw[file_name]
        ms, = struct.unpack_from(">I", raw, 0x14)
        do, = struct.unpack_from(">q", raw, 0x20)
        assert do == (0x30 + ms + 15) // 16 * 16, "data_offset fora do padrão align16"
        objs = sorted(f.objects.values(), key=lambda o: o.path_id)
        first = struct.pack("<q", objs[0].path_id)
        meta, p, cnt_at = bytes(raw[:do]), -1, None
        while cnt_at is None:  # 1ª entrada da tabela: o path_id pode aparecer antes em outro lugar do metadata
            p = meta.find(first, p + 1)
            assert p > 0, "tabela de objetos não encontrada"
            cnt_at = next((c for c in range(p - 4, p - 8, -1) if struct.unpack_from("<i", raw, c)[0] == len(objs)),
                          None)
        table = [struct.unpack_from("<qqIi", raw, p + 24 * i) for i in range(len(objs))]
        data = bytearray(raw[do:])
        for pid, tid, b in new:
            assert all(pid != e[0] for e in table)
            data.extend(b"\0" * ((-len(data)) % 16))
            table.append((pid, len(data), len(b), tid))
            data.extend(b)
        table.sort()
        meta = bytearray(raw[0x30:p]) + b"".join(struct.pack("<qqIi", *e) for e in table)
        meta += raw[p + 24 * len(objs):0x30 + ms]
        struct.pack_into("<i", meta, cnt_at - 0x30, len(table))
        head = bytearray(raw[:0x30])
        ndo = (0x30 + len(meta) + 15) // 16 * 16
        struct.pack_into(">I", head, 0x14, len(meta))
        struct.pack_into(">q", head, 0x20, ndo)
        out = head + meta + b"\0" * (ndo - 0x30 - len(meta)) + data
        struct.pack_into(">q", out, 0x18, len(out))
        self.raw[file_name] = out

    def replace_texture(self, tex_obj, img):
        """Troca os pixels de um Texture2D que mora no .resS, no lugar (mesmo tamanho). RGBA32 linear vai cru;
        ASTC e o que tem m_PlatformBlob (swizzle block-linear do Switch) passam pelo encoder do UnityPy com o
        mesmo blob — round-trip offline conferido no ForestTexturePacked (mesmo tamanho, erro médio ~0,1/255)."""
        from PIL import Image
        from UnityPy.export.Texture2DConverter import image_to_texture2d
        d = tex_obj.read()
        sd = d.m_StreamData
        # com mips (ex.: vfx, 12 níveis) só o nível 0 é reescrito; o mundo é desenhado pixel-perfect (sem minificar)
        assert img.size == (d.m_Width, d.m_Height), (img.size, d.m_Width, d.m_Height)
        res = sd.path.rsplit("/", 1)[-1]
        if d.m_TextureFormat == 4 and not d.m_PlatformBlob:
            px = img.convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM).tobytes()  # Unity guarda de baixo pra cima
        else:
            px, _ = image_to_texture2d(img.convert("RGBA"), d.m_TextureFormat, 38, d.m_PlatformBlob)  # 38 = Switch
        if not sd.size:  # pixels dentro do próprio objeto (ex.: tps_lossless_icons em resources.assets)
            tree = tex_obj.read_typetree()
            assert len(px) == len(tree["image data"]), (len(px), len(tree["image data"]))
            tree["image data"] = px
            fname = next(n for n, f in self.bundle.files.items() if f is tex_obj.assets_file)
            self.replace_object(fname, tex_obj, typetree_bytes(tex_obj, tree))
            return
        assert len(px) == sd.size or (d.m_MipCount > 1 and len(px) < sd.size), (len(px), sd.size)
        self.raw[res][sd.offset:sd.offset + len(px)] = px

    def set_texture_rgba(self, tex_obj, img):
        """Reescreve um Texture2D de qualquer formato/tamanho como RGBA32 linear com os pixels dentro do objeto
        (sem .resS, sem blob, sem mip). Pro que o encoder não refaz (DXT1Crunched) ou quando o tamanho muda."""
        from PIL import Image
        tree = tex_obj.read_typetree()
        px = img.convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM).tobytes()
        tree.update({"m_Width": img.width, "m_Height": img.height, "m_TextureFormat": 4, "m_MipCount": 1,
                     "m_IsPreProcessed": False, "m_CompleteImageSize": len(px), "image data": px})
        tree["m_PlatformBlob"] = type(tree["m_PlatformBlob"])()
        tree["m_StreamData"] = {**tree["m_StreamData"], "offset": 0, "size": 0, "path": ""}
        fname = next(n for n, f in self.bundle.files.items() if f is tex_obj.assets_file)
        self.replace_object(fname, tex_obj, typetree_bytes(tex_obj, tree))

    def upscale_atlas(self, tex_obj, d):
        """Atlas d× mais denso: imagem ampliada em NEAREST (sprites não trocados ficam idênticos) e todo sprite do
        bundle que aponta pra ela com campos em pixel ×d e PPU 100·d+1 (malha em unidades fica; o hook SpriteRect
        devolve rect/pivô em 1× pro código do VS). Devolve (imagem, k): quem chama pinta por cima com os rects lidos
        ANTES ×k (os ObjectReader do UnityPy ficam com os valores velhos) e grava com set_texture_rgba. Idempotente:
        atlas já marcado (overlay relido) devolve k=1 e não mexe em nada."""
        from PIL import Image
        img = tex_obj.read().image.convert("RGBA")
        tfile = next(n for n, f in self.bundle.files.items() if f is tex_obj.assets_file)
        mul = lambda v: {a: x * d for a, x in v.items()}
        hits = []
        for fn, f in self.serialized():
            ext = [e.path.rsplit("/", 1)[-1] for e in f.externals]
            for o in list(f.objects.values()):
                if o.type.name != "Sprite":
                    continue
                t = o.read_typetree()
                r = t["m_RD"]["texture"]
                if (fn if r["m_FileID"] == 0 else ext[r["m_FileID"] - 1]) == tfile and r["m_PathID"] == tex_obj.path_id:
                    hits.append((fn, o, t))
        if any(round(t["m_PixelsToUnits"]) % 100 == 1 for _, _, t in hits):
            return img, 1
        for fn, o, t in hits:
            for k in ("m_Rect", "m_Offset", "m_Border"):
                t[k] = mul(t[k])
            t["m_PixelsToUnits"] = t["m_PixelsToUnits"] * d + 1  # +1 = marca pro hook SpriteRect (main.cpp)
            for k in ("textureRect", "textureRectOffset", "atlasRectOffset", "uvTransform"):
                t["m_RD"][k] = mul(t["m_RD"][k])
            t["m_RD"]["uvTransform"]["x"] = t["m_RD"]["uvTransform"]["z"] = t["m_PixelsToUnits"]
            self.replace_object(fn, o, typetree_bytes(o, t))
        return img.resize((img.width * d, img.height * d), Image.NEAREST), d

    def save(self, path):
        b = self.bundle
        for n, f in list(b.files.items()):
            flags = f.flags
            b.files[n] = EndianBinaryReader(bytes(self.raw[n]))
            b.files[n].flags = flags  # flag do nó no diretório (4 = SerializedFile, 0 = .resS)
        # mesmos flags do original (0x243 = LZ4HC + blocos no início com padding)
        data = b.save(packer=(int(b.dataflags), int(b._block_info_flags)))
        open(path, "wb").write(data)
        return len(data)


def typetree_bytes(obj, tree) -> bytes:
    """Serializa um objeto editado pelo typetree sem mexer no estado do ObjectReader (round-trip conferido em
    Sprite e Texture2D dos bundles; o problema do UnityPy é só no SerializedFile inteiro)."""
    from UnityPy.helpers import TypeTreeHelper
    from UnityPy.streams import EndianBinaryWriter
    w = EndianBinaryWriter(endian=obj.reader.endian)
    TypeTreeHelper.write_typetree(tree, obj._get_typetree_node(None), w, obj.assets_file)
    return w.bytes


class I2Terms:
    """MonoBehaviour I2Languages (sem typetree: IL2CPP). Layout verificado nos bytes do VS 1.15.113:
    cabeçalho até a contagem de termos; termo = Term str, TermType i32, Languages str[], Flags byte[],
    Languages_Touch str[]; depois o resto do objeto (idiomas, assets) vai intacto."""

    def __init__(self, raw: bytes, count_at=56):
        self.raw, p = raw, count_at
        n = struct.unpack_from("<i", raw, p)[0]
        p += 4
        self.head, self.terms = raw[:p], []
        for _ in range(n):
            term, p = self._s(p)
            ttype = struct.unpack_from("<i", raw, p)[0]
            langs, p = self._sa(p + 4)
            nf = struct.unpack_from("<i", raw, p)[0]
            flags = raw[p + 4:p + 4 + nf]
            p += 4 + nf + (-nf) % 4
            touch, p = self._sa(p)
            self.terms.append([term, ttype, langs, flags, touch])
        self.tail = raw[p:]
        self.index = {t[0]: t for t in self.terms}

    def _s(self, p):
        n = struct.unpack_from("<i", self.raw, p)[0]
        return self.raw[p + 4:p + 4 + n].decode("utf-8"), p + 4 + n + (-n) % 4

    def _sa(self, p):
        n = struct.unpack_from("<i", self.raw, p)[0]
        p += 4
        out = []
        for _ in range(n):
            s, p = self._s(p)
            out.append(s)
        return out, p

    def save(self) -> bytes:
        def s(x):
            b = x.encode("utf-8")
            return struct.pack("<i", len(b)) + b + b"\0" * ((-len(b)) % 4)
        out = [self.head]
        for term, ttype, langs, flags, touch in self.terms:
            out += [s(term), struct.pack("<ii", ttype, len(langs)), *map(s, langs),
                    struct.pack("<i", len(flags)), flags, b"\0" * ((-len(flags)) % 4),
                    struct.pack("<i", len(touch)), *map(s, touch)]
        return b"".join(out) + self.tail


def text_asset_bytes(name: str, script: bytes) -> bytes:
    def s(b):
        return struct.pack("<i", len(b)) + b + b"\0" * ((-len(b)) % 4)
    return s(name.encode()) + s(script)


if __name__ == "__main__":
    # self-check: o layout gerado bate com o objeto original do jogo
    import sys
    bd = Bundle(sys.argv[1])
    for n, f in bd.serialized():
        for o in f.objects.values():
            if o.type.name == "TextAsset":
                d = o.read()
                sc = d.m_Script.encode("utf-8", "surrogateescape") if isinstance(d.m_Script, str) else d.m_Script
                assert text_asset_bytes(d.m_Name, sc) == o.get_raw_data(), d.m_Name
    print("ok: text_asset_bytes == raw para todos os TextAssets")
    if len(sys.argv) > 2:  # add_objects sem objetos reproduz o arquivo; com um, o UnityPy lê de volta
        bd = Bundle(sys.argv[2]); (n, f), = bd.serialized(); orig = bytes(bd.raw[n])
        bd.add_objects(n, []); assert bytes(bd.raw[n]) == orig
        s = next(o for o in f.objects.values() if o.type.name == "Sprite")
        bd.add_objects(n, [(12345, list(f.types).index(s.serialized_type), s.get_raw_data())])
        f2 = SerializedFile(EndianBinaryReader(bytes(bd.raw[n])), name=n)
        assert f2.objects[12345].read().m_Name == s.read().m_Name and len(f2.objects) == len(f.objects) + 1
        assert all(f2.objects[k].get_raw_data() == o.get_raw_data() for k, o in f.objects.items())
        print("ok: add_objects")
