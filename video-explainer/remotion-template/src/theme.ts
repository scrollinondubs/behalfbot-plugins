export const COL = {
  ink: '#191c21',
  grey: '#6e747d',
  bg: '#fcfbf8',
  red: '#d62d2d',
  blue: '#1e5fdc',
  amber: '#e89614',
  green: '#149664',
} as const;

export type ColorName = keyof typeof COL;

export const colorOf = (name: string | undefined): string =>
  (COL as Record<string, string>)[name ?? 'red'] ?? COL.red;

export const FONT_STACK = 'Helvetica, Arial, "Liberation Sans", sans-serif';
