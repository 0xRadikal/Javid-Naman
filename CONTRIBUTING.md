# راهنمای مشارکت / Contributing Guide

از مشارکت شما سپاسگزاریم. این آرشیو زنده است و با کمک شما کامل‌تر می‌شود.
Thank you for contributing. This is a living archive and grows with your help.

## 🇮🇷 فارسی

### چه چیزهایی می‌پذیریم

- ✅ افزودن نام جان‌باختگان جدید از میان مردم (با حداقل یک منبع معتبر)
- ✅ تکمیل اطلاعات رکوردهای موجود (شهر، تاریخ، شرح، منبع، عکس)
- ✅ اصلاح خطاهای املایی، تاریخ یا اطلاعات
- ✅ افزودن منابع تازه برای رکوردهای «گزارش‌شده» تا به «مستند» ارتقا یابند
- ✅ بهبود رابط کاربری، دسترس‌پذیری و SEO

### چه چیزهایی نمی‌پذیریم

- ❌ افزودن نیروهای حکومتی، بسیج، سپاه یا سازمان‌های سرکوبگر
- ❌ رکورد بدون هیچ منبع
- ❌ محتوای توهین‌آمیز یا غیرمحترمانه نسبت به جان‌باختگان

### استانداردهای داده

هر رکورد جاویدنام باید با [`assets/data/person.schema.json`](./assets/data/person.schema.json) سازگار باشد:

- `id` با الگوی `jvn_[0-9a-f]{10}` (از `sha1(نام نرمال‌شده + '|' + رویداد)`)
- حداقل یک منبع در آرایهٔ `sources`
- `verification` برابر `documented` (دو منبع مستقل یا نهاد حقوق بشری) یا `reported`
- زبان محترمانه و بی‌طرف در `story` و `cause`

### روند مشارکت

1. مخزن را Fork کنید.
2. تغییرات را در یک شاخهٔ جدید اعمال کنید.
3. اگر داده اضافه می‌کنید، رکورد را به `assets/data/javidnam.json` بیفزایید و منبع را ذکر کنید.
4. یک Pull Request با شرح روشن باز کنید.

---

## 🇬🇧 English

### What we accept

- Adding newly documented victims **from among the people** (with at least one credible source)
- Completing existing records (city, date, story, source, photo)
- Fixing typos, dates, or factual errors
- Adding fresh sources to upgrade `reported` records to `documented`
- UI, accessibility, and SEO improvements

### What we do **not** accept

- Regime forces, Basij, IRGC, or repressive organizations
- Records with no source whatsoever
- Disrespectful or defamatory content

### Data standards

Each record must conform to [`person.schema.json`](./assets/data/person.schema.json):
a valid `jvn_...` id, at least one `sources` entry, a proper `verification`
level, and respectful, neutral language.

### Workflow

1. Fork the repository.
2. Make changes on a new branch.
3. For data, add the record to `assets/data/javidnam.json` with a source.
4. Open a Pull Request with a clear description.

---

با احترام، یاد همهٔ جان‌باختگان راه آزادی گرامی باد.
