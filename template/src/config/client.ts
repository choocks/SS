/**
 * SINGLE SOURCE OF TRUTH for all client-specific content.
 *
 * Cloning a new client = edit this file + drop real photos in /public/images/.
 * Do NOT hardcode copy, prices, phone numbers, or colors anywhere else.
 *
 * IMPORTANT: use real photos of the client's business, staff, and work.
 * No stock-photo cliches (no smiling-headset call centers, no faux-handshakes,
 * no AI-generated imagery). A bad real photo converts better than a great
 * stock photo.
 */

export interface ClientConfig {
  brand: {
    name: string;
    primaryColor: string;
    primaryColorDark: string;
    foregroundOnBrand: string;
    fontHeading: string;
    fontBody: string;
  };
  meta: {
    domain: string;
    title: string;
    description: string;
    favicon: string;
  };
  contact: {
    phoneDisplay: string;
    phoneTel: string;
    email: string;
    addressLine: string;
    hours: string;
  };
  hero: {
    eyebrow?: string;
    headline: string;
    subhead: string;
    primaryCtaLabel: string;
    image: string;
    imageAlt: string;
    imageWidth: number;
    imageHeight: number;
  };
  trustMarkers: string[];
  socialProof: {
    headline?: string;
    items: { label: string; sub?: string }[];
  };
  problem: {
    headline: string;
    subhead?: string;
    points: { title: string; body: string }[];
  };
  offer: {
    headline: string;
    subhead?: string;
    bullets: string[];
    price?: string;
    priceNote?: string;
    ctaLabel: string;
  };
  testimonials: {
    headline?: string;
    items: { quote: string; name: string; result?: string }[];
  };
  faq: {
    headline?: string;
    items: { q: string; a: string }[];
  };
  finalCta: {
    headline: string;
    subhead?: string;
    ctaLabel: string;
  };
  form: {
    web3formsKey: string;
    fieldType: 'phone' | 'email';
    placeholder: string;
    consentText: string;
    redirectUrl?: string;
  };
  analytics: {
    plausibleDomain: string;
  };
  footer: {
    legalName: string;
    license?: string;
    privacyUrl?: string;
    termsUrl?: string;
  };
}

export const client: ClientConfig = {
  brand: {
    name: 'Sunrise Med Spa',
    primaryColor: '#0F766E',       // teal-700
    primaryColorDark: '#115E59',   // teal-800
    foregroundOnBrand: '#FFFFFF',
    fontHeading:
      "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontBody:
      "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },

  meta: {
    domain: 'sunrisemedspa.com',
    title: 'Sunrise Med Spa — Botox & Filler in Austin, TX',
    description:
      'Award-winning injectors, transparent pricing, and natural-looking results. Book a free consultation in under 60 seconds.',
    favicon: '/favicon.svg',
  },

  contact: {
    phoneDisplay: '(512) 555-0142',
    phoneTel: '+15125550142',
    email: 'hello@sunrisemedspa.com',
    addressLine: '512 Lamar Blvd, Austin, TX 78704',
    hours: 'Mon–Sat 9am–6pm',
  },

  hero: {
    eyebrow: 'Austin · South Lamar',
    headline: 'Botox & filler that looks like you, only rested.',
    subhead:
      'Master injectors with 12+ years of experience. Transparent pricing, no upsell, results you can see in 7 days.',
    primaryCtaLabel: 'Book free consultation',
    // TODO replace with a real photo of the clinic, lead injector, or a treatment room.
    image: '/images/hero.svg',
    imageAlt: 'Lead injector consulting with a patient in the Sunrise treatment room.',
    imageWidth: 1200,
    imageHeight: 900,
  },

  trustMarkers: [
    '4.9★ from 287 Google reviews',
    '12+ years in business',
    'TX MD license #ABC123',
  ],

  socialProof: {
    headline: 'Trusted by Austin since 2012',
    items: [
      { label: '4.9 / 5', sub: '287 Google reviews' },
      { label: '8,200+', sub: 'treatments delivered' },
      { label: '12 yrs', sub: 'in business' },
      { label: 'A+', sub: 'BBB rating' },
    ],
  },

  problem: {
    headline: 'You should know exactly what you’re paying for. And what you’re not.',
    subhead:
      'Most med spas hide pricing, push packages you don’t need, and leave you guessing about results.',
    points: [
      {
        title: 'Transparent, per-unit pricing',
        body:
          'Published pricing on every service. No “consultation required to see prices,” no surprise add-ons.',
      },
      {
        title: 'No package pressure',
        body:
          'Pay as you go. Buy a package only if it’s genuinely cheaper for what you actually need.',
      },
      {
        title: 'Master injectors only',
        body:
          'Every treatment is performed by an injector with 5+ years of experience. No trainees on paying clients.',
      },
    ],
  },

  offer: {
    headline: 'Free 20-minute consultation',
    subhead:
      'Sit down with a master injector, get a treatment plan with exact pricing, and decide on your own time. No pressure.',
    bullets: [
      'Honest assessment — we’ll tell you if you don’t need a treatment',
      'Written pricing you can take home',
      'Same-day booking available if you’re ready',
      'Ten-minute parking right out front',
    ],
    price: 'Free',
    priceNote: 'Normally $75. Free this month for new clients.',
    ctaLabel: 'Book my consultation',
  },

  testimonials: {
    headline: 'Recent results',
    items: [
      {
        quote:
          'I’ve been to four med spas in Austin. Sunrise is the only one that didn’t try to upsell me. Walked out with a plan I can actually afford.',
        name: 'Jen M.',
        result: 'Botox + lip filler · Aug 2025',
      },
      {
        quote:
          'Subtle, natural results. My friends noticed something looked good but couldn’t place what changed.',
        name: 'Priya R.',
        result: 'Tear-trough filler · Jul 2025',
      },
      {
        quote:
          'Twelve years and still my go-to. They remember my history every visit and never push me into anything.',
        name: 'Carla S.',
        result: 'Long-time client',
      },
    ],
  },

  faq: {
    headline: 'Common questions',
    items: [
      {
        q: 'How much does Botox cost?',
        a:
          '$13 per unit. A typical treatment is 20–40 units. We’ll tell you exactly how many you need at your free consultation.',
      },
      {
        q: 'Do you take walk-ins?',
        a:
          'Same-day appointments are usually available. Booking ahead guarantees your preferred injector and time.',
      },
      {
        q: 'Will I look “done”?',
        a:
          'Not unless you ask us to. Our default is subtle and natural — friends notice you look rested, not different.',
      },
      {
        q: 'Is there parking?',
        a:
          'Free 10-minute parking right out front, plus a paid lot next door if our spaces are full.',
      },
    ],
  },

  finalCta: {
    headline: 'See what your treatment plan would actually cost.',
    subhead:
      'No pressure, no obligation. Twenty minutes with a master injector and you’ll walk out with a written plan.',
    ctaLabel: 'Book free consultation',
  },

  form: {
    web3formsKey: 'YOUR_WEB3FORMS_ACCESS_KEY',
    fieldType: 'phone',
    placeholder: 'Your mobile number',
    consentText:
      'By submitting, you agree we may text you to confirm your appointment. Standard rates apply. We never share your info.',
    redirectUrl: 'https://sunrisemedspa.com/thanks',
  },

  analytics: {
    plausibleDomain: 'sunrisemedspa.com',
  },

  footer: {
    legalName: 'Sunrise Aesthetics, LLC',
    license: 'TX MD license #ABC123',
    privacyUrl: '/privacy',
    termsUrl: '/terms',
  },
};
