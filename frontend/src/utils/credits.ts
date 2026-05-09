export const CREDITS_EXHAUSTED =
  (import.meta.env.VITE_CREDITS_EXHAUSTED ?? 'true') !== 'false';

export const DEMO_CONTACT_EMAIL = 's3sarwar@uwaterloo.ca';

export const DEMO_MAILTO = `mailto:${DEMO_CONTACT_EMAIL}?subject=${encodeURIComponent(
  'ArchFlow demo request'
)}`;
