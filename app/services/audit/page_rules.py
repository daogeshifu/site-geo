"""Detailed checks derived exclusively from the requested document, without I/O."""
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlparse

from app.utils.url_utils import normalize_url


def detailed_page_checks(soup, parsed, url, response, *, is_product, zh=True):
    checks = []

    def add(key, passed, label, evidence, fix, *, advisory=False):
        # Keep concrete Chinese evidence for the Chinese export; English clients
        # can still consume stable keys, severity, measured values and pass state.
        checks.append({"key": key, "passed": bool(passed), "label": label,
                       "evidence": evidence, "recommendation": None if passed else fix,
                       "severity": "advisory" if advisory else "issue",
                       "scope": "response_html"})

    titles = soup.find_all('title')
    descriptions = soup.find_all('meta', attrs={'name': re.compile('^description$', re.I)})
    title = parsed['title'] or ''
    description = parsed['meta_description'] or ''
    add('title_unique',len(titles)==1,'title 标签数量不为 1',f'检测到 {len(titles)} 个 title 标签','保留一个与当前页面内容一致的 title。')
    if title:
        add('title_length',30<=len(title)<=65,'标题长度需复核',f'title 为 {len(title)} 个字符：{title[:180]}','按目标语言和搜索展示检查标题宽度及截断风险；字符数仅为参考。',advisory=True)
    add('description_unique',len(descriptions)<=1,'存在重复的 meta description',f'检测到 {len(descriptions)} 个 description 标签','合并为一条描述当前页面的 description。')
    if description:
        add('description_length',70<=len(description)<=170,'页面描述长度需复核',f'description 为 {len(description)} 个字符','按目标语言检查摘要是否过短或易截断；字符数仅为参考。',advisory=True)
    canonicals = soup.find_all('link',rel=lambda v:v and 'canonical' in v)
    add('canonical_unique',len(canonicals)<=1,'存在多个 canonical 声明',f'检测到 {len(canonicals)} 个 canonical 标签','只保留一个明确的规范链接。')
    if canonicals:
        canonical = urljoin(url,canonicals[0].get('href') or '')
        target = urlparse(canonical)
        add('canonical_http',bool(canonicals[0].get('href')) and target.scheme in {'http','https'} and bool(target.netloc),'canonical 地址无效',f'canonical={canonicals[0].get("href")!r}','使用有效的 HTTP/HTTPS 规范页面地址。')
        add('canonical_fragment',not target.fragment,'canonical 包含片段标识',f'canonical={canonical}','规范链接中去掉 # 片段标识。')
        add('canonical_target',normalize_url(canonical)==normalize_url(url),'canonical 指向其他 URL，需确认归一意图',f'当前 URL={url}；canonical={canonical}','确认该页是否应归并到此 canonical；不要自动改成自引用。',advisory=True)
    all_headings=soup.find_all(re.compile('^h[1-6]$'))
    empty_headings=[h.name for h in all_headings if not h.get_text(' ',strip=True)]
    add('empty_headings',not empty_headings,'存在空标题标签',f'{len(empty_headings)} 个空标题标签：{", ".join(empty_headings[:8])}','删除空标题或补充实际标题文本。')
    levels=[int(h['level'][1]) for h in parsed['headings']]
    jumps=[f'h{a}→h{b}' for a,b in zip(levels,levels[1:]) if b>a+1]
    add('heading_order',not jumps,'标题层级存在跳级',f'检测到 {len(jumps)} 处：{", ".join(jumps[:8])}','检查内容分节，按语义安排标题层级。',advisory=True)
    non_h1=[h['text'].strip().lower() for h in parsed['headings'] if h['level']!='h1']
    duplicates=[(t,n) for t,n in Counter(non_h1).items() if n>1]
    add('heading_duplicates',not duplicates,'页面内存在重复分节标题',f'{len(duplicates)} 种重复标题；示例：'+str(duplicates[:3]),'核对是否为重复导航或重复内容组件；按实际用途优化。',advisory=True)
    viewport=parsed.get('viewport') or ''
    if viewport:
        add('viewport_device_width','width=device-width' in viewport.replace(' ',''),'viewport 未使用设备宽度',f'viewport={viewport}','检查移动端布局是否需要 width=device-width。',advisory=True)
        add('viewport_zoom',not re.search(r'user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:\.0)?(?:\s|,|$)',viewport,re.I),'页面限制用户缩放',f'viewport={viewport}','允许用户缩放以改善可访问性。')
    from bs4 import BeautifulSoup
    main=BeautifulSoup(str(soup.body or soup),'lxml')
    for tag in main.find_all(['nav','header','footer','script','style','noscript','template']):
        tag.decompose()
    main_text=main.get_text(' ',strip=True)
    word_count=len(main_text.split())
    add('main_content_depth',word_count>=150,'去除导航等组件后页面正文偏少',f'约 {word_count} 个空白分词；这是静态 HTML 文本统计','核对商品说明、规格与购买信息是否仅由 JavaScript 注入；按实际页面补充可抓取内容。',advisory=True)
    imgs=soup.find_all('img')
    informative=[i for i in imgs if i.get('role') not in {'presentation','none'} and i.get('aria-hidden')!='true']
    missing=[i for i in imgs if not i.has_attr('alt')]
    empty=[i for i in informative if i.has_attr('alt') and not i.get('alt','').strip()]
    dimensions=[i for i in imgs if not (i.get('width') and i.get('height'))]
    if imgs:
        add('image_alt_empty',not empty,'部分非显式装饰图片使用空 alt，需人工确认',f'{len(empty)}/{len(imgs)} 张；示例：'+str([i.get('src') or i.get('data-src') for i in empty[:3]]),'区分商品图与装饰图；商品等信息图片提供描述性 alt。',advisory=True)
        add('image_dimensions',not dimensions,'部分图片未声明 width/height',f'{len(dimensions)}/{len(imgs)} 张图片未同时声明尺寸','检查 CSS 是否已预留宽高比；缺少空间预留时补充尺寸以降低布局偏移风险。',advisory=True)
    anchors=soup.find_all('a',href=True)
    def accessible_name(a):
        return a.get_text(' ',strip=True) or a.get('aria-label') or a.get('title') or ' '.join(i.get('alt','') for i in a.find_all('img'))
    unnamed=[a for a in anchors if not accessible_name(a) and not a.get('aria-labelledby') and not a.find('svg')]
    add('link_names',not unnamed,'存在未检测到可访问名称的链接',f'{len(unnamed)}/{len(anchors)} 个；示例：'+str([a['href'] for a in unnamed[:3]]),'检查这些链接是否具有文字、aria-label、关联名称或图片替代文本。',advisory=True)
    mixed=[]
    if urlparse(url).scheme=='https':
        mixed=[t.get('src') or t.get('href') for t in soup.find_all(['script','img','link','iframe']) if str(t.get('src') or t.get('href') or '').startswith('http://')]
    add('mixed_content',not mixed,'HTTPS 页面引用 HTTP 资源',f'{len(mixed)} 处；示例：'+str(mixed[:3]),'将页面资源改为可用的 HTTPS 地址。')
    blocking=[s.get('src') for s in soup.select('head script[src]') if not s.has_attr('async') and not s.has_attr('defer') and s.get('type','').lower() not in {'module','application/ld+json','application/json'}]
    add('head_blocking_scripts',not blocking,'head 中存在潜在阻塞解析的脚本',f'{len(blocking)} 个；示例：'+str(blocking[:3]),'核对脚本依赖后使用 defer/async；该检查不代表已测得加载性能。',advisory=True)
    raw_bytes=len(response.content)
    add('html_size',raw_bytes<=250000,'HTML 响应体较大',f'解码后的响应体 {raw_bytes:,} 字节','检查内联脚本、重复模板和冗余标记；此项不是压缩传输体积或真实加载时间。',advisory=True)
    invalid=[]
    nodes=[]
    def walk(obj):
        if isinstance(obj,dict):
            nodes.append(obj)
            for value in obj.values():walk(value)
        elif isinstance(obj,list):
            for value in obj:walk(value)
    for index,script in enumerate(soup.find_all('script',attrs={'type':'application/ld+json'}),1):
        try:walk(json.loads(script.string or script.get_text()))
        except (ValueError,TypeError):invalid.append(index)
    add('jsonld_valid',not invalid,'JSON-LD 不是有效 JSON',f'无法解析的 JSON-LD 块序号：{invalid}','修复 JSON 语法后再验证结构化数据。')
    def has_type(node,name):
        types=node.get('@type',[])
        return name.lower() in [str(t).lower() for t in (types if isinstance(types,list) else [types])]
    # A ProductGroup can inherit display data from its variants. Do not apply
    # individual Product fields to the group container.
    products=[n for n in nodes if has_type(n,'Product')]
    def populated(obj,key):
        value=obj.get(key)
        return value is not None and value!='' and value!=[] and value!={}
    if is_product and products:
        for key,label in [('name','名称'),('image','图片'),('description','描述')]:
            missing_fields=[i for i,p in enumerate(products,1) if not populated(p,key)]
            add('product_'+key,not missing_fields,f'部分 Product 数据缺少{label}',f'{len(missing_fields)}/{len(products)} 个 Product 节点缺少 {key}；序号：{missing_fields[:10]}',f'为当前商品结构化数据补充真实的 {key}。',advisory=key=='description')
        offers=[n for n in nodes if has_type(n,'Offer') or has_type(n,'AggregateOffer')]
        has_offers=any(populated(p,'offers') for p in products)
        add('product_offers',has_offers,'Product 未声明 offers 购买信息',f'{len(products)} 个 Product 节点；含 offers：{sum(populated(p,"offers") for p in products)}','若该页用于直接购买，补充与可见价格、币种、库存一致的 offers；非销售页需人工判断。',advisory=True)
        # Embedded offers need not declare @type explicitly.
        for p in products:
            value=p.get('offers')
            for obj in value if isinstance(value,list) else [value]:
                if isinstance(obj,dict) and obj not in offers:offers.append(obj)
        if offers:
            for key,label in [('priceCurrency','币种'),('availability','库存状态')]:
                count=sum(not populated(o,key) for o in offers)
                add('offer_'+key,count==0,f'部分 Offer 未声明{label}',f'{count}/{len(offers)} 个 Offer 缺少 {key}',f'按页面实际商品信息补充 {key}。',advisory=True)
            count=sum(not any(populated(o,k) for k in ['price','lowPrice','priceSpecification']) for o in offers)
            add('offer_price',count==0,'部分 Offer 未声明价格',f'{count}/{len(offers)} 个 Offer 缺少 price/lowPrice/priceSpecification','按实际售价补充价格字段；禁止编造价格。',advisory=True)
    languages=soup.find_all('link',hreflang=True)
    if languages:
        invalid=[(t.get('hreflang'),t.get('href')) for t in languages if not t.get('href') or not re.fullmatch(r'(?:[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*|x-default)',t.get('hreflang',''))]
        add('hreflang_syntax',not invalid,'hreflang 声明格式或地址缺失',f'{len(invalid)}/{len(languages)} 条；示例：{invalid[:3]}','修复语言代码和对应页面地址；未访问其他语言页面验证回链。')
        duplicate_languages=[(k,n) for k,n in Counter(t.get('hreflang','').lower() for t in languages).items() if n>1]
        add('hreflang_duplicates',not duplicate_languages,'同一语言有重复 hreflang 声明',f'重复语言：{duplicate_languages[:5]}','核对是否给同一语言声明了冲突地址。',advisory=True)
    # Meta-only social checks are optional enhancements, never hard errors.
    og=parsed.get('open_graph') or {}
    add('open_graph',bool(og.get('og:title') and og.get('og:description') and og.get('og:image')),'社交分享元数据不完整',f'已声明 Open Graph 字段：{list(og)}','按分享需求补齐 og:title、og:description 和 og:image。',advisory=True)
    return checks
