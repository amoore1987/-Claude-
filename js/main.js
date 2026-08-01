/* Jen Jenivive — concept redesign. Vanilla JS, no dependencies. */
(function () {
  'use strict';

  var D = window.JJ_DATA;
  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var byHandle = {};
  D.books.concat(D.custom, D.merch, D.bundles, [D.club]).forEach(function (b) { byHandle[b.h] = b; });

  function coverSrc(h) {
    // single-file builds embed covers as data URIs in window.JJ_IMG
    return (window.JJ_IMG && window.JJ_IMG[h]) || 'assets/covers/' + h + '.webp';
  }
  function productUrl(h) { return 'https://jenjenivive.com/products/' + h; }
  function gbp(p) { return p ? '£' + p : ''; }
  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }

  /* ---------- cheeky gate ---------- */
  var gate = document.getElementById('gate');
  var seen = false;
  try { seen = sessionStorage.getItem('jj-adult') === 'yes'; } catch (e) {}
  var gateYes = document.getElementById('gateYes');
  if (seen) {
    gate.classList.add('is-open');
  } else {
    document.body.style.overflow = 'hidden';
    setTimeout(function () { gateYes.focus(); }, 100);
    gate.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var focusables = gate.querySelectorAll('button, a[href]');
      var first = focusables[0], last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }
  gateYes.addEventListener('click', function () {
    try { sessionStorage.setItem('jj-adult', 'yes'); } catch (e) {}
    confettiBurst();
    gate.classList.add('is-open');
    document.body.style.overflow = '';
    var h1 = document.getElementById('heroTitle');
    if (h1) h1.focus({ preventScroll: true });
  });

  /* ---------- confetti ---------- */
  var canvas = document.getElementById('confetti');
  var ctx = canvas.getContext('2d');
  var pieces = [];
  var confettiRunning = false;
  var COLORS = ['#FAB3F8', '#CD3A8E', '#B8A9E0', '#FDDD0F', '#8FC4F7', '#ffffff'];
  function sizeCanvas() { canvas.width = innerWidth; canvas.height = innerHeight; }
  sizeCanvas();
  addEventListener('resize', sizeCanvas);
  function confettiBurst(x, y, n) {
    if (prefersReduced) return;
    x = x == null ? innerWidth / 2 : x;
    y = y == null ? innerHeight * 0.4 : y;
    n = n || 130;
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, v = 5 + Math.random() * 9;
      pieces.push({
        x: x, y: y,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v - 4,
        w: 6 + Math.random() * 7, h: 8 + Math.random() * 9,
        r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.35,
        c: COLORS[(Math.random() * COLORS.length) | 0],
        life: 90 + Math.random() * 60
      });
    }
    if (!confettiRunning) { confettiRunning = true; requestAnimationFrame(confettiTick); }
  }
  function confettiTick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces = pieces.filter(function (p) { return p.life > 0; });
    pieces.forEach(function (p) {
      p.x += p.vx; p.y += p.vy; p.vy += 0.28; p.vx *= 0.985; p.r += p.vr; p.life--;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.r);
      ctx.globalAlpha = Math.min(1, p.life / 40);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });
    if (pieces.length) requestAnimationFrame(confettiTick);
    else { confettiRunning = false; ctx.clearRect(0, 0, canvas.width, canvas.height); }
  }

  /* ---------- header + progress + cursor ---------- */
  var hdr = document.getElementById('hdr');
  var progress = document.getElementById('progress');
  var ticking = false;
  addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      hdr.classList.toggle('is-stuck', scrollY > 30);
      var max = document.documentElement.scrollHeight - innerHeight;
      progress.style.transform = 'scaleX(' + (max > 0 ? scrollY / max : 0) + ')';
      ticking = false;
    });
  }, { passive: true });

  var blob = document.getElementById('cursorBlob');
  if (!prefersReduced && matchMedia('(pointer: fine)').matches) {
    var bx = -100, by = -100, tx = -100, ty = -100;
    addEventListener('mousemove', function (e) { tx = e.clientX; ty = e.clientY; }, { passive: true });
    document.addEventListener('mouseover', function (e) {
      blob.classList.toggle('is-hovering', !!e.target.closest('a, button, input'));
    });
    (function blobTick() {
      bx += (tx - bx) * 0.18; by += (ty - by) * 0.18;
      blob.style.left = bx + 'px'; blob.style.top = by + 'px';
      requestAnimationFrame(blobTick);
    })();
  } else {
    blob.remove();
  }

  /* ---------- mobile nav ---------- */
  var burger = document.getElementById('burger');
  var nav = document.getElementById('nav');
  function setNav(open) {
    nav.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', open);
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) { var f = nav.querySelector('a'); if (f) f.focus(); }
    else burger.focus();
  }
  burger.addEventListener('click', function () { setNav(!nav.classList.contains('is-open')); });
  nav.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') setNav(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && nav.classList.contains('is-open')) setNav(false);
  });

  /* ---------- split letters (hero h1) ---------- */
  document.querySelectorAll('[data-splitletters]').forEach(function (h) {
    var i = 0;
    h.setAttribute('aria-label', h.textContent.trim());
    (function split(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) {
          var frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(function (word) {
            if (!word) return;
            if (/^\s+$/.test(word)) { frag.appendChild(document.createTextNode(' ')); return; }
            var w = el('span', 'sl-word');
            word.split('').forEach(function (ch) {
              var s = el('span', 'sl-letter', ch);
              s.style.setProperty('--i', i++);
              s.setAttribute('aria-hidden', 'true');
              w.appendChild(s);
            });
            frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) split(child);
      });
    })(h);
  });
  // trigger letter animation once fonts are in (avoids FOUT mid-bounce)
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { document.body.classList.add('fonts-ready'); });
    setTimeout(function () { document.body.classList.add('fonts-ready'); }, 1200);
  } else {
    document.body.classList.add('fonts-ready');
  }

  /* ---------- hero floating covers ---------- */
  var HERO_BOOKS = [
    { h: 'the-little-bean',          w: 38, x: 28, y: 22, r: -7,  depth: 1.6, dur: 5.2, del: 0 },
    { h: 'my-best-friends-are-balls', w: 30, x: 2,  y: 4,  r: -12, depth: 0.9, dur: 6.1, del: -1.4 },
    { h: 'fisting',                  w: 27, x: 66, y: 0,  r: 10,  depth: 1.2, dur: 5.7, del: -2.6 },
    { h: 'my-beaver-loves-wood',     w: 26, x: 4,  y: 58, r: 8,   depth: 1.9, dur: 4.9, del: -0.8 },
    { h: 'my-fat-pussy',             w: 27, x: 68, y: 52, r: -9,  depth: 1.4, dur: 6.4, del: -3.2 }
  ];
  var stack = document.getElementById('heroStack');
  HERO_BOOKS.forEach(function (b, idx) {
    var book = byHandle[b.h];
    if (!book) return;
    var a = el('a', 'hero-book');
    a.href = productUrl(b.h);
    a.target = '_blank'; a.rel = 'noopener';
    a.style.cssText = '--w:' + b.w + '%; --r:' + b.r + 'deg; --dur:' + b.dur + 's; --del:' + b.del + 's;' +
      'left:' + b.x + '%; top:' + b.y + '%; --z:' + (idx === 0 ? 5 : 3) + ';';
    a.dataset.depth = b.depth;
    a.innerHTML = '<img src="' + coverSrc(b.h) + '" alt="' + esc(book.t) + '" width="' + book.w + '" height="' + book.ht + '" loading="eager">';
    stack.appendChild(a);
  });

  // mouse parallax on hero covers
  if (!prefersReduced && matchMedia('(pointer: fine)').matches) {
    var hero = document.querySelector('.hero');
    var books = stack.querySelectorAll('.hero-book');
    var pmx = 0, pmy = 0, cmx = 0, cmy = 0, parallaxOn = false;
    hero.addEventListener('mousemove', function (e) {
      var r = hero.getBoundingClientRect();
      pmx = (e.clientX - r.left) / r.width - 0.5;
      pmy = (e.clientY - r.top) / r.height - 0.5;
      if (!parallaxOn) { parallaxOn = true; requestAnimationFrame(parallaxTick); }
    }, { passive: true });
    function parallaxTick() {
      cmx += (pmx - cmx) * 0.06; cmy += (pmy - cmy) * 0.06;
      books.forEach(function (b) {
        var d = parseFloat(b.dataset.depth);
        b.style.marginLeft = (-cmx * d * 26) + 'px';
        b.style.marginTop = (-cmy * d * 20) + 'px';
      });
      if (Math.abs(pmx - cmx) < 0.001 && Math.abs(pmy - cmy) < 0.001) { parallaxOn = false; return; }
      requestAnimationFrame(parallaxTick);
    }
  }

  /* ---------- marquees: duplicate content for seamless loop ---------- */
  document.querySelectorAll('[data-marquee]').forEach(function (track) {
    track.appendChild(track.firstElementChild.cloneNode(true));
  });

  /* ---------- scroll reveal ---------- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) {
        en.target.classList.add('in-view');
        io.unobserve(en.target);
      }
    });
  }, { threshold: 0.18, rootMargin: '0px 0px -6% 0px' });

  document.querySelectorAll('[data-anim], h2, .about-quote').forEach(function (n) { io.observe(n); });
  document.querySelectorAll('[data-stagger]').forEach(function (wrap) {
    Array.prototype.forEach.call(wrap.children, function (c, i) {
      c.style.setProperty('--d', (i * 0.09).toFixed(2) + 's');
    });
  });

  /* ---------- counters ---------- */
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      cio.unobserve(en.target);
      var n = en.target, target = +n.dataset.count, suffix = n.dataset.suffix || '';
      if (prefersReduced) { n.textContent = target + suffix; return; }
      n.textContent = '0' + suffix;
      var t0 = null;
      (function step(ts) {
        if (!t0) t0 = ts;
        var p = Math.min(1, (ts - t0) / 1400);
        var eased = 1 - Math.pow(1 - p, 3);
        n.textContent = Math.round(target * eased) + suffix;
        if (p < 1) requestAnimationFrame(step);
      })(performance.now());
    });
  }, { threshold: 0.6 });
  document.querySelectorAll('.stat-num').forEach(function (n) { cio.observe(n); });

  /* ---------- best sellers shelf ---------- */
  var shelf = document.getElementById('shelf');
  var RANKS = ['No.1', 'No.2', 'No.3', 'No.4', 'No.5', 'No.6', 'No.7', 'No.8', 'No.9', 'No.10'];
  D.best.forEach(function (h, i) {
    var b = byHandle[h];
    if (!b) return;
    var card = el('a', 'book-card');
    card.href = productUrl(h); card.target = '_blank'; card.rel = 'noopener';
    card.style.setProperty('--rot', ((i % 2 ? 1 : -1) * (0.6 + (i % 3) * 0.5)).toFixed(1) + 'deg');
    card.innerHTML =
      '<span class="book-3d">' +
        '<span class="book-cover">' +
          '<span class="book-spine"></span>' +
          '<img src="' + coverSrc(h) + '" alt="" width="' + b.w + '" height="' + b.ht + '" loading="lazy">' +
          '<span class="book-rank">' + RANKS[i] + '</span>' +
          (b.p ? '<span class="book-price">' + gbp(b.p) + '</span>' : '') +
        '</span>' +
      '</span>' +
      '<span class="book-title">' + esc(b.t) + '</span>';
    shelf.appendChild(card);
  });

  // drag to scroll with momentum
  (function () {
    var isDown = false, startX = 0, startLeft = 0, vel = 0, lastX = 0, momentumId = null;
    shelf.addEventListener('pointerdown', function (e) {
      isDown = true; startX = lastX = e.clientX; startLeft = shelf.scrollLeft; vel = 0;
      cancelAnimationFrame(momentumId);
      shelf.classList.add('is-dragging');
    });
    addEventListener('pointermove', function (e) {
      if (!isDown) return;
      vel = e.clientX - lastX; lastX = e.clientX;
      shelf.scrollLeft = startLeft - (e.clientX - startX);
    }, { passive: true });
    function endDrag(withMomentum) {
      if (!isDown) return;
      isDown = false;
      shelf.classList.remove('is-dragging');
      if (!withMomentum) return;
      (function momentum() {
        if (Math.abs(vel) < 0.4) return;
        shelf.scrollLeft -= vel;
        vel *= 0.94;
        momentumId = requestAnimationFrame(momentum);
      })();
    }
    addEventListener('pointerup', function () { endDrag(true); });
    addEventListener('pointercancel', function () { endDrag(false); });
    shelf.addEventListener('lostpointercapture', function () { endDrag(false); });
    shelf.addEventListener('dragstart', function (e) { e.preventDefault(); });
    // suppress accidental link clicks after a drag
    shelf.addEventListener('click', function (e) {
      if (Math.abs(lastX - startX) > 6) { e.preventDefault(); e.stopPropagation(); }
    }, true);
  })();

  /* ---------- library ---------- */
  var grid = document.getElementById('libGrid');
  var libEmpty = document.getElementById('libEmpty');
  var searchInput = document.getElementById('libSearch');
  var bestSet = {}, newSet = {};
  D.best.forEach(function (h) { bestSet[h] = 1; });
  D.new.forEach(function (h) { newSet[h] = 1; });
  document.getElementById('bookCount').textContent = D.books.length;

  var currentFilter = 'all';
  var tileIO = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) {
        en.target.classList.add('is-shown');
        tileIO.unobserve(en.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px 8% 0px' });

  function libraryItems() {
    var items;
    if (currentFilter === 'best') items = D.books.filter(function (b) { return bestSet[b.h]; });
    else if (currentFilter === 'new') items = D.books.filter(function (b) { return newSet[b.h]; });
    else if (currentFilter === 'bundles') items = D.bundles.slice();
    else items = D.books.slice();
    var q = searchInput.value.trim().toLowerCase();
    if (q) items = items.filter(function (b) { return b.t.toLowerCase().indexOf(q) !== -1; });
    return items;
  }

  function renderLibrary(shuffled) {
    var items = libraryItems();
    if (shuffled) {
      for (var i = items.length - 1; i > 0; i--) {
        var j = (Math.random() * (i + 1)) | 0, tmp = items[i]; items[i] = items[j]; items[j] = tmp;
      }
    }
    grid.innerHTML = '';
    libEmpty.hidden = items.length > 0;
    var status = document.getElementById('libStatus');
    if (status) status.textContent = items.length
      ? items.length + (items.length === 1 ? ' book shown' : ' books shown')
      : 'No books match — try another word';
    items.forEach(function (b, i) {
      var t = el('a', 'tile');
      t.href = productUrl(b.h); t.target = '_blank'; t.rel = 'noopener';
      t.style.setProperty('--rot', (((i * 7) % 5) - 2) * 0.7 + 'deg');
      t.style.setProperty('--d', ((i % 12) * 0.05).toFixed(2) + 's');
      t.setAttribute('aria-label', b.t + (b.p ? ', ' + gbp(b.p) : ''));
      t.innerHTML =
        '<img src="' + coverSrc(b.h) + '" alt="" loading="lazy" width="' + b.w + '" height="' + b.ht + '">' +
        '<span class="tile-info" aria-hidden="true">' +
          '<span class="tile-name">' + esc(b.t) + '</span>' +
          (b.p ? '<span class="tile-price">' + gbp(b.p) + '</span>' : '') +
          '<span class="tile-view">Peek inside →</span>' +
        '</span>';
      grid.appendChild(t);
      if (prefersReduced) t.classList.add('is-shown');
      else tileIO.observe(t);
    });
  }
  renderLibrary();

  document.querySelectorAll('.chip[data-filter]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      document.querySelectorAll('.chip[data-filter]').forEach(function (c) {
        c.classList.remove('is-active');
        c.setAttribute('aria-pressed', 'false');
      });
      chip.classList.add('is-active');
      chip.setAttribute('aria-pressed', 'true');
      currentFilter = chip.dataset.filter;
      renderLibrary();
    });
  });
  document.getElementById('shuffleBtn').addEventListener('click', function (e) {
    renderLibrary(true);
    var r = e.target.getBoundingClientRect();
    confettiBurst(r.left + r.width / 2, r.top, 50);
  });
  var searchT;
  searchInput.addEventListener('input', function () {
    clearTimeout(searchT);
    searchT = setTimeout(function () { renderLibrary(); }, 160);
  });

  /* ---------- personalised: slot machine + deck ---------- */
  var slotWord = document.getElementById('slotWord');
  var deck = document.getElementById('persDeck');
  var persTitles = D.custom.map(function (c) { return c.t.replace(/^Customised\s+/i, '').replace(/!.*$/, ''); });
  var deckCards = [];
  D.custom.forEach(function (c, i) {
    var card = el('div', 'deck-card');
    card.innerHTML = '<img src="' + coverSrc(c.h) + '" alt="' + esc(c.t) + '" loading="lazy" width="' + c.w + '" height="' + c.ht + '">';
    deck.appendChild(card);
    deckCards.push(card);
  });
  var persIdx = 0;
  function setDeck() {
    var n = deckCards.length;
    deckCards.forEach(function (c, i) {
      c.className = 'deck-card' +
        (i === persIdx ? ' is-front' :
         i === (persIdx + 1) % n ? ' is-right' :
         i === (persIdx - 1 + n) % n ? ' is-left' : '');
    });
  }
  setDeck();
  if (!prefersReduced) {
    setInterval(function () {
      slotWord.classList.add('roll-out');
      setTimeout(function () {
        persIdx = (persIdx + 1) % deckCards.length;
        slotWord.textContent = persTitles[persIdx];
        slotWord.classList.remove('roll-out');
        slotWord.classList.add('roll-in');
        setDeck();
        setTimeout(function () { slotWord.classList.remove('roll-in'); }, 400);
      }, 280);
    }, 2600);
  }

  /* ---------- book club parcel ---------- */
  var clubImg = document.getElementById('clubBookImg');
  clubImg.src = coverSrc(D.club.h);
  clubImg.alt = D.club.t;
  var priceEl = document.getElementById('clubPrice');
  if (D.club.p) priceEl.textContent = gbp(D.club.p);
  var parcel = document.getElementById('clubParcel');
  var pio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) {
        parcel.classList.add('is-open');
        pio.unobserve(parcel);
      }
    });
  }, { threshold: 0.55 });
  pio.observe(parcel);

  /* ---------- merch line ---------- */
  var line = document.getElementById('merchLine');
  D.merch.forEach(function (m, i) {
    var item = el('a', 'merch-item');
    item.href = productUrl(m.h); item.target = '_blank'; item.rel = 'noopener';
    item.style.setProperty('--del', (-(i % 5) * 0.9).toFixed(1) + 's');
    item.innerHTML =
      '<span class="merch-peg"></span>' +
      '<span class="merch-img"><img src="' + coverSrc(m.h) + '" alt="" loading="lazy" width="' + m.w + '" height="' + m.ht + '"></span>' +
      '<span class="merch-name">' + esc(m.t) + '</span>';
    line.appendChild(item);
  });

  /* ---------- reviews ---------- */
  var bubbles = document.getElementById('bubbles');
  D.reviews.forEach(function (r) {
    var b = el('article', 'bubble');
    b.setAttribute('data-anim', 'pop');
    var stars = '';
    for (var i = 0; i < 5; i++) stars += '<span style="--i:' + i + '" aria-hidden="true">★</span>';
    b.innerHTML =
      '<div class="bubble-stars" role="img" aria-label="5 out of 5 stars">' + stars + '</div>' +
      '<p class="bubble-q">“' + esc(r.q) + '”</p>' +
      '<div class="bubble-meta"><span class="bubble-name">' + esc(r.n) + '</span>' +
      '<span class="bubble-book">' + esc(r.b) + '</span></div>';
    bubbles.appendChild(b);
    io.observe(b);
  });
  Array.prototype.forEach.call(bubbles.children, function (c, i) {
    c.style.setProperty('--d', (i * 0.09).toFixed(2) + 's');
  });

  /* ---------- library tiles: tap once on touch shows info ---------- */
  if (matchMedia('(pointer: coarse)').matches) {
    grid.addEventListener('click', function (e) {
      var tile = e.target.closest('.tile');
      if (!tile) return;
      if (!tile.classList.contains('is-tapped')) {
        e.preventDefault();
        grid.querySelectorAll('.is-tapped').forEach(function (t) { t.classList.remove('is-tapped'); });
        tile.classList.add('is-tapped');
      }
    });
  }
})();
