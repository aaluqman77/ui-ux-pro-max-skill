# UI/UX Pro Max - MCP Server

Membungkus mesin cari BM25 di `src/ui-ux-pro-max/` jadi **remote MCP server**
(Streamable HTTP), supaya bisa dipasang sebagai konektor di Claude web/mobile -
bukan cuma sebagai skill lokal di Claude Code.

## Kenapa ini masuk akal jadi konektor

`core.py` adalah fungsi murni: query masuk, hasil ranking keluar. Tanpa state,
tanpa auth pengguna, tanpa data pribadi, tanpa tulis ke disk. Itu bentuk tool
MCP yang ideal.

## Tool yang diekspos

| Tool | Fungsi |
|---|---|
| `ui_search` | Cari di 11 domain: style, color, typography, google-fonts, icons, chart, landing, product, ux, react, web |
| `ui_stack_guidelines` | Guideline + contoh kode per framework (22 stack) |
| `ui_design_system` | Generate design system utuh sekali jalan |
| `ui_capabilities` | Daftar semua domain & stack yang tersedia |

## Environment variable

| Nama | Wajib | Keterangan |
|---|---|---|
| `MCP_SECRET` | ya (di publik) | Segmen path rahasia. Endpoint jadi `/mcp/<MCP_SECRET>` |
| `PORT` | tidak | Diisi otomatis oleh Railway. Default 8080 |
| `LOG_LEVEL` | tidak | Default `info` |

Tanpa `MCP_SECRET`, endpoint jatuh ke `/mcp` tanpa proteksi apa pun. Jangan
dipakai di deployment publik.

## Cek sehat

`GET /` atau `GET /healthz` balas JSON `{"ok": true, ...}` tanpa perlu rahasia -
karena tidak membocorkan apa pun selain jumlah domain & stack.

## Jalan lokal

```bash
pip install -r requirements.txt
MCP_SECRET=dev PORT=8080 python mcp_server/server.py
# endpoint: http://localhost:8080/mcp/dev
```

## Atribusi

Repo ini fork dari [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
(MIT). Seluruh data CSV dan mesin cari di `src/ui-ux-pro-max/` adalah karya
upstream. Berkas `LICENSE` tidak boleh dihapus.
