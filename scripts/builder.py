"""
data/posts/{id}/ → html/index.html
Галерея с 5 табами: Посты / Инструменты / Workflow / Категории / Недоступные
Alpine.js + Tailwind CSS
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import iter_posts  # noqa: E402


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru" x-data="app()" x-init="init()" @keydown.escape.window="onEscape()">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Save-Inst</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <style>
    [x-cloak] { display: none !important; }
    .card-media { aspect-ratio: 1/1; object-fit: cover; }
    video.card-media { background: #111; }
    .tab-active { @apply bg-pink-600 text-white; }
    .lightbox-img { max-height: 90vh; max-width: 90vw; object-fit: contain; }
  </style>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen" x-cloak>

<!-- ============================================================ HEADER -->
<header class="sticky top-0 z-40 bg-gray-900 border-b border-gray-800 px-4 py-3">
  <div class="flex flex-wrap gap-3 items-center mb-2">
    <span class="text-lg font-bold text-pink-400">Save-Inst</span>

    <!-- Search (only posts tab) -->
    <template x-if="tab === 'posts'">
      <input
        x-model="search"
        type="text"
        placeholder="Поиск…"
        class="flex-1 min-w-[180px] max-w-xs bg-gray-800 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-pink-500"
      />
    </template>
    <template x-if="tab === 'tools'">
      <input
        x-model="toolSearch"
        type="text"
        placeholder="Поиск инструмента…"
        class="flex-1 min-w-[180px] max-w-xs bg-gray-800 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-pink-500"
      />
    </template>

    <!-- Type filter (posts tab only) -->
    <template x-if="tab === 'posts'">
      <div class="flex gap-1 flex-wrap">
        <template x-for="t in types" :key="t">
          <button
            @click="typeFilter = typeFilter === t ? '' : t"
            :class="typeFilter === t ? 'bg-pink-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'"
            class="px-2.5 py-1 rounded-lg text-xs font-medium transition"
            x-text="t"
          ></button>
        </template>
      </div>
    </template>

    <!-- Count -->
    <span class="text-xs text-gray-500 ml-auto" x-text="statusText"></span>
  </div>

  <!-- Category filter row (posts tab) -->
  <template x-if="tab === 'posts'">
    <div class="flex gap-2 overflow-x-auto pb-1">
      <button
        @click="catFilter = ''"
        :class="catFilter === '' ? 'bg-pink-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'"
        class="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition flex-shrink-0"
      >Все</button>
      <template x-for="c in allCategories" :key="c">
        <button
          @click="catFilter = catFilter === c ? '' : c"
          :class="catFilter === c ? 'bg-pink-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'"
          class="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition flex-shrink-0"
          x-text="c + ' (' + countByCategory(c) + ')'"
        ></button>
      </template>
    </div>
  </template>

  <!-- Tabs nav -->
  <nav class="flex gap-1 mt-2 border-t border-gray-800 pt-2">
    <template x-for="t in tabs" :key="t.id">
      <button
        @click="switchTab(t.id)"
        :class="tab === t.id ? 'bg-pink-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition"
        x-text="t.label"
      ></button>
    </template>
  </nav>
</header>

<!-- ============================================================ TAB: POSTS -->
<main x-show="tab === 'posts'" class="p-4">
  <div class="columns-2 sm:columns-3 md:columns-4 lg:columns-5 xl:columns-6 gap-3 space-y-3">
    <template x-for="post in filteredPosts" :key="post.id">
      <div
        class="break-inside-avoid cursor-pointer rounded-xl overflow-hidden bg-gray-900 border border-gray-800 hover:border-pink-500 transition group mb-3"
        @click="openModal(post)"
      >
        <!-- Media preview -->
        <div class="relative">
          <template x-if="isVideo(post) && post.thumbnail">
            <img :src="post.thumbnail" class="w-full aspect-square object-cover" loading="lazy" />
          </template>
          <template x-if="isVideo(post) && !post.thumbnail">
            <div class="aspect-square w-full bg-gray-800 flex flex-col items-center justify-center gap-1">
              <div class="text-4xl text-gray-500">▶</div>
              <div class="text-[10px] text-gray-600 uppercase tracking-wide" x-text="post.type || 'video'"></div>
            </div>
          </template>
          <template x-if="!isVideo(post) && post.media && post.media.length > 0">
            <img
              :src="post.media[0]"
              :alt="post.author"
              class="w-full"
              loading="lazy"
              @click.stop="openLightbox(post.media[0])"
            />
          </template>
          <template x-if="!post.media || post.media.length === 0">
            <div class="aspect-square w-full bg-gray-800 flex items-center justify-center text-gray-600 text-3xl">?</div>
          </template>
          <!-- Type badge -->
          <span
            class="absolute top-1.5 right-1.5 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded"
            x-text="post.type"
          ></span>
          <!-- Carousel count -->
          <template x-if="post.type === 'carousel'">
            <span class="absolute top-1.5 left-1.5 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded">
              1/<span x-text="post.media.length"></span>
            </span>
          </template>
        </div>
        <!-- Card info -->
        <div class="p-2">
          <div class="flex items-center gap-1 mb-1">
            <span class="text-[10px] font-semibold bg-pink-900/60 text-pink-300 px-1.5 py-0.5 rounded-full" x-text="post.category || 'Other'"></span>
            <span class="text-[10px] text-gray-500" x-text="post.date ? post.date.slice(0,10) : ''"></span>
          </div>
          <!-- Tools chips -->
          <template x-if="post.tools && post.tools.length > 0">
            <div class="flex flex-wrap gap-1 mb-1">
              <template x-for="tool in post.tools.slice(0,3)" :key="tool">
                <span class="text-[9px] bg-gray-800 text-gray-400 px-1 py-0.5 rounded" x-text="tool"></span>
              </template>
              <template x-if="post.tools.length > 3">
                <span class="text-[9px] text-gray-600" x-text="'+' + (post.tools.length - 3)"></span>
              </template>
            </div>
          </template>
          <div class="text-[10px] text-gray-400 line-clamp-2" x-text="post.insight"></div>
        </div>
      </div>
    </template>
  </div>

  <div x-show="filteredPosts.length === 0" class="text-center text-gray-600 py-20 text-lg">
    Ничего не найдено
  </div>
</main>

<!-- ============================================================ TAB: TOOLS -->
<main x-show="tab === 'tools'" class="p-4 max-w-3xl mx-auto">
  <div class="space-y-2">
    <template x-for="item in filteredTools" :key="item.tool">
      <div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <button
          class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800 transition text-left"
          @click="item.open = !item.open"
        >
          <span class="font-medium text-white" x-text="item.tool"></span>
          <div class="flex items-center gap-3">
            <span class="text-sm text-pink-400 font-semibold" x-text="item.posts.length + ' постов'"></span>
            <span class="text-gray-500 text-sm" x-text="item.open ? '▲' : '▼'"></span>
          </div>
        </button>
        <template x-if="item.open">
          <div class="border-t border-gray-800 p-3 space-y-2">
            <template x-for="pid in item.posts" :key="pid">
              <div
                class="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-800 cursor-pointer transition"
                @click="openModalById(pid)"
              >
                <template x-if="getPost(pid) && getPost(pid).media && getPost(pid).media.length > 0">
                  <template x-if="!isVideoSrc(getPost(pid).media[0])">
                    <img :src="getPost(pid).media[0]" class="w-12 h-12 rounded object-cover flex-shrink-0" loading="lazy" />
                  </template>
                  <template x-if="isVideoSrc(getPost(pid).media[0]) && getPost(pid).thumbnail">
                    <img :src="getPost(pid).thumbnail" class="w-12 h-12 rounded object-cover flex-shrink-0" loading="lazy" />
                  </template>
                  <template x-if="isVideoSrc(getPost(pid).media[0]) && !getPost(pid).thumbnail">
                    <div class="w-12 h-12 rounded bg-gray-800 flex items-center justify-center flex-shrink-0 text-gray-500 text-xl">▶</div>
                  </template>
                </template>
                <div class="min-w-0">
                  <div class="text-sm text-gray-200 truncate" x-text="getPost(pid) ? ('@' + getPost(pid).author) : pid"></div>
                  <div class="text-xs text-gray-500 line-clamp-2" x-text="getPost(pid) ? getPost(pid).insight : ''"></div>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </template>
  </div>
  <div x-show="filteredTools.length === 0" class="text-center text-gray-600 py-20 text-lg">Инструменты не найдены</div>
</main>

<!-- ============================================================ TAB: WORKFLOW -->
<main x-show="tab === 'workflow'" class="p-4 max-w-5xl mx-auto">
  <template x-for="group in workflowGroups" :key="group.value_type">
    <div class="mb-8">
      <h2 class="text-lg font-bold text-pink-400 mb-3 flex items-center gap-2">
        <span x-text="group.value_type"></span>
        <span class="text-sm text-gray-500 font-normal" x-text="'(' + group.posts.length + ')'"></span>
      </h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <template x-for="post in group.posts" :key="post.id">
          <div
            class="bg-gray-900 border border-gray-800 rounded-xl p-3 cursor-pointer hover:border-pink-500 transition"
            @click="openModal(post)"
          >
            <div class="flex items-start gap-2 mb-2">
              <template x-if="post.media && post.media.length > 0">
                <template x-if="!isVideoSrc(post.media[0])">
                  <img :src="post.media[0]" class="w-14 h-14 rounded-lg object-cover flex-shrink-0" loading="lazy" />
                </template>
                <template x-if="isVideoSrc(post.media[0]) && post.thumbnail">
                  <img :src="post.thumbnail" class="w-14 h-14 rounded-lg object-cover flex-shrink-0" loading="lazy" />
                </template>
                <template x-if="isVideoSrc(post.media[0]) && !post.thumbnail">
                  <div class="w-14 h-14 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0 text-gray-500 text-2xl">▶</div>
                </template>
              </template>
              <div class="min-w-0">
                <div class="text-xs text-gray-400 truncate" x-text="'@' + post.author"></div>
                <div class="text-sm text-gray-200 line-clamp-2 mt-0.5" x-text="post.insight"></div>
              </div>
            </div>
            <!-- Workflow chain -->
            <template x-if="post.workflow && post.workflow.length > 0">
              <ol class="mt-2 space-y-1">
                <template x-for="(step, idx) in post.workflow" :key="idx">
                  <li class="flex items-start gap-1.5 text-[11px] text-gray-400">
                    <span class="text-pink-500 font-bold flex-shrink-0" x-text="(idx+1) + '.'"></span>
                    <span x-text="step"></span>
                  </li>
                </template>
              </ol>
            </template>
          </div>
        </template>
      </div>
    </div>
  </template>
  <div x-show="workflowGroups.length === 0" class="text-center text-gray-600 py-20 text-lg">Нет данных</div>
</main>

<!-- ============================================================ TAB: CATEGORIES -->
<main x-show="tab === 'categories'" class="p-4 max-w-4xl mx-auto">
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
    <template x-for="cat in categoryStats" :key="cat.name">
      <button
        @click="switchTab('posts'); catFilter = cat.name"
        class="bg-gray-900 border border-gray-800 hover:border-pink-500 rounded-xl p-4 text-left transition group"
      >
        <div class="text-2xl font-bold text-pink-400 group-hover:text-pink-300" x-text="cat.count"></div>
        <div class="text-sm font-medium text-white mt-1" x-text="cat.name"></div>
        <div class="text-xs text-gray-500 mt-0.5">постов</div>
      </button>
    </template>
  </div>
</main>

<!-- ============================================================ TAB: UNAVAILABLE -->
<main x-show="tab === 'unavailable'" class="p-4">
  <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-w-4xl mx-auto">
    <template x-for="post in errorPosts" :key="post.id">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-3">
        <div class="text-sm font-medium text-gray-300 mb-1" x-text="'@' + (post.author || post.id)"></div>
        <div class="text-xs text-gray-500 mb-2" x-text="post.date ? post.date.slice(0,10) : ''"></div>
        <a
          :href="post.url"
          target="_blank"
          class="inline-block text-xs text-pink-400 hover:text-pink-300 underline break-all"
          x-text="post.url"
        ></a>
      </div>
    </template>
  </div>
  <div x-show="errorPosts.length === 0" class="text-center text-gray-600 py-20 text-lg">Нет недоступных постов</div>
</main>

<!-- ============================================================ MODAL -->
<div
  x-show="modal"
  @click.self="closeModal()"
  class="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-4"
>
  <div
    x-show="modal"
    x-transition
    class="bg-gray-900 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-gray-700"
  >
    <template x-if="modal">
      <div class="p-4">
        <!-- Header -->
        <div class="flex justify-between items-start mb-3">
          <div>
            <div class="font-semibold text-white" x-text="'@' + modal.author"></div>
            <div class="text-xs text-gray-400" x-text="modal.date ? modal.date.slice(0,10) : ''"></div>
          </div>
          <button @click="closeModal()" class="text-gray-500 hover:text-white text-2xl leading-none">&times;</button>
        </div>

        <!-- Gallery -->
        <div class="space-y-2 mb-4">
          <template x-for="(src, idx) in modal.media" :key="idx">
            <div>
              <template x-if="isVideoSrc(src)">
                <video :src="src" controls class="w-full rounded-lg max-h-96 bg-black"></video>
              </template>
              <template x-if="!isVideoSrc(src)">
                <img
                  :src="src"
                  class="w-full rounded-lg max-h-96 object-contain bg-black cursor-zoom-in"
                  loading="lazy"
                  @click.stop="openLightbox(src)"
                />
              </template>
            </div>
          </template>
        </div>

        <!-- Category + value_type + tools -->
        <div class="flex flex-wrap gap-1.5 mb-3">
          <span class="bg-pink-900/60 text-pink-300 text-xs px-2 py-0.5 rounded-full" x-text="modal.category || 'Other'"></span>
          <template x-if="modal.value_type">
            <span class="bg-blue-900/60 text-blue-300 text-xs px-2 py-0.5 rounded-full" x-text="modal.value_type"></span>
          </template>
          <template x-for="tool in (modal.tools || [])" :key="tool">
            <span class="bg-gray-800 text-gray-300 text-xs px-2 py-0.5 rounded-full" x-text="tool"></span>
          </template>
        </div>

        <!-- Insight -->
        <div x-show="modal.insight" class="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3 italic" x-text="modal.insight"></div>

        <!-- Workflow -->
        <template x-if="modal.workflow && modal.workflow.length > 0">
          <div class="bg-gray-800 rounded-lg px-3 py-2 mb-3">
            <div class="text-xs text-gray-500 font-semibold uppercase mb-2">Workflow</div>
            <ol class="space-y-1">
              <template x-for="(step, idx) in modal.workflow" :key="idx">
                <li class="flex items-start gap-2 text-sm text-gray-300">
                  <span class="text-pink-400 font-bold flex-shrink-0" x-text="idx+1 + '.'"></span>
                  <span x-text="step"></span>
                </li>
              </template>
            </ol>
          </div>
        </template>

        <!-- Description -->
        <details class="mb-3">
          <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-300">Описание</summary>
          <p class="text-sm text-gray-400 mt-2 whitespace-pre-wrap" x-text="modal.description"></p>
        </details>

        <!-- Hashtags -->
        <template x-if="modal.hashtags && modal.hashtags.length > 0">
          <div class="flex flex-wrap gap-1 mb-3">
            <template x-for="tag in modal.hashtags.slice(0,15)" :key="tag">
              <span class="bg-gray-800 text-gray-500 text-[10px] px-1.5 py-0.5 rounded" x-text="tag"></span>
            </template>
          </div>
        </template>

        <!-- Actions -->
        <div class="flex gap-2">
          <a
            :href="modal.url"
            target="_blank"
            class="flex-1 text-center bg-gradient-to-r from-pink-600 to-purple-600 text-white text-sm py-2 rounded-lg hover:opacity-90 transition"
          >Открыть в Instagram</a>
          <button
            @click="copyLink(modal.url)"
            class="bg-gray-800 text-gray-300 text-sm px-4 py-2 rounded-lg hover:bg-gray-700 transition"
            x-text="copied ? 'Скопировано!' : 'Копировать'"
          ></button>
        </div>
      </div>
    </template>
  </div>
</div>

<!-- ============================================================ LIGHTBOX -->
<div
  x-show="lightbox"
  @click="lightbox = null"
  class="fixed inset-0 z-[60] bg-black/95 flex items-center justify-center cursor-zoom-out"
>
  <img
    x-show="lightbox"
    :src="lightbox"
    class="lightbox-img rounded shadow-2xl"
    @click.stop
  />
  <button
    @click="lightbox = null"
    class="absolute top-4 right-4 text-white text-3xl leading-none hover:text-pink-400 transition"
  >&times;</button>
</div>

<script src="data/posts.js"></script>
<script>
function app() {
  return {
    allPosts: [],
    search: '',
    catFilter: '',
    typeFilter: '',
    toolSearch: '',
    tab: 'posts',
    tabs: [
      { id: 'posts',       label: 'Посты' },
      { id: 'tools',       label: 'Инструменты' },
      { id: 'workflow',    label: 'Workflow' },
      { id: 'categories',  label: 'Категории' },
      { id: 'unavailable', label: 'Недоступные' },
    ],
    modal: null,
    lightbox: null,
    copied: false,
    toolsData: window.TOOLS_DATA || {},
    valuesData: window.VALUES_DATA || {},

    init() {
      this.allPosts = (window.POSTS_DATA || []);
    },

    switchTab(id) {
      this.tab = id;
    },

    onEscape() {
      if (this.lightbox) { this.lightbox = null; return; }
      if (this.modal) { this.closeModal(); return; }
    },

    // ---------- posts ----------
    get posts() {
      return this.allPosts.filter(p => !p.fetch_error);
    },

    get errorPosts() {
      return this.allPosts.filter(p => p.fetch_error);
    },

    get allCategories() {
      const s = new Set();
      this.posts.forEach(p => { if (p.category) s.add(p.category); });
      return [...s].sort();
    },

    get types() {
      return [...new Set(this.posts.map(p => p.type).filter(Boolean))].sort();
    },

    get filteredPosts() {
      const q = this.search.toLowerCase();
      return this.posts.filter(p => {
        if (this.typeFilter && p.type !== this.typeFilter) return false;
        if (this.catFilter && p.category !== this.catFilter) return false;
        if (q) {
          const text = [p.author, p.description, p.insight,
            ...(p.hashtags || []), ...(p.tools || [])].join(' ').toLowerCase();
          if (!text.includes(q)) return false;
        }
        return true;
      });
    },

    countByCategory(cat) {
      return this.posts.filter(p => p.category === cat).length;
    },

    get statusText() {
      if (this.tab === 'posts') return this.filteredPosts.length + ' постов';
      if (this.tab === 'unavailable') return this.errorPosts.length + ' недоступных';
      return '';
    },

    // ---------- tools ----------
    get toolsList() {
      const map = {};
      this.posts.forEach(p => {
        (p.tools || []).forEach(t => {
          if (!t) return;
          if (!map[t]) map[t] = [];
          map[t].push(p.id);
        });
      });
      return Object.entries(map)
        .sort((a, b) => b[1].length - a[1].length)
        .map(([tool, posts]) => ({ tool, posts, open: false }));
    },

    get filteredTools() {
      const q = this.toolSearch.toLowerCase();
      if (!q) return this.toolsList;
      return this.toolsList.filter(item => item.tool.toLowerCase().includes(q));
    },

    // ---------- workflow ----------
    get workflowGroups() {
      const map = {};
      this.posts.forEach(p => {
        const vt = p.value_type || 'другое';
        if (!map[vt]) map[vt] = [];
        map[vt].push(p);
      });
      return Object.entries(map)
        .sort((a, b) => b[1].length - a[1].length)
        .map(([value_type, posts]) => ({ value_type, posts }));
    },

    // ---------- categories ----------
    get categoryStats() {
      return this.allCategories.map(c => ({
        name: c,
        count: this.countByCategory(c),
      })).sort((a, b) => b.count - a.count);
    },

    // ---------- modal / lightbox ----------
    getPost(id) {
      return this.posts.find(p => p.id === id) || null;
    },

    openModal(post) {
      this.modal = post;
      this.copied = false;
    },

    openModalById(id) {
      const p = this.getPost(id);
      if (p) this.openModal(p);
    },

    closeModal() {
      this.modal = null;
    },

    openLightbox(src) {
      this.lightbox = src;
    },

    isVideo(post) {
      return post.media?.length > 0 && this.isVideoSrc(post.media[0]);
    },

    isVideoSrc(src) {
      return /\.(mp4|webm|mov)$/i.test(src || '');
    },

    async copyLink(url) {
      try {
        await navigator.clipboard.writeText(url);
        this.copied = true;
        setTimeout(() => (this.copied = false), 2000);
      } catch {}
    },
  };
}
</script>
</body>
</html>
"""


def main():
    posts = list(iter_posts(with_enriched=True))

    # Write posts.js — media paths need ../ prefix because index.html is in html/
    display_posts = copy.deepcopy(posts)
    for p in display_posts:
        p['media'] = ['../' + m for m in p.get('media', [])]
        if p.get('thumbnail'):
            p['thumbnail'] = '../' + p['thumbnail']

    html_data = Path('html/data')
    html_data.mkdir(parents=True, exist_ok=True)

    (html_data / 'posts.js').write_text(
        'window.POSTS_DATA = ' + json.dumps(display_posts, ensure_ascii=False, indent=2) + ';\n'
    )

    # Write index.html
    html_dir = Path('html')
    html_dir.mkdir(exist_ok=True)
    (html_dir / 'index.html').write_text(HTML_TEMPLATE)

    ok = sum(1 for p in posts if not p.get('fetch_error'))
    err = sum(1 for p in posts if p.get('fetch_error'))
    print(f'Built html/index.html  ({ok} posts, {err} unavailable)')
    print('Open html/index.html in browser to view')


if __name__ == '__main__':
    main()
