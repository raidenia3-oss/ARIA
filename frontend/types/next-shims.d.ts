// Ambient type shims for the `next/*` modules.
//
// The locally installed `next` (v9.3.3 in node_modules) predates the App
// Router / `next/server` / `next/font/google` APIs the codebase uses, so the
// real type declarations are absent. These shims let `tsc --noEmit` and the
// local ESLint run against the actual code without a framework reinstall.
// They intentionally model only the surface the project uses.

declare module "next/server" {
  export class NextResponse {
    headers: Headers;
    status: number;
    constructor(body?: BodyInit | null, init?: ResponseInit);
    static json(body: unknown, init?: ResponseInit): NextResponse & Response;
    static redirect(url: string, init?: number | ResponseInit): NextResponse &
      Response;
    static next(init?: ResponseInit): NextResponse & Response;
  }

  export interface NextRequest extends Request {
    url: string;
    text(): Promise<string>;
    json(): Promise<unknown>;
    formData(): Promise<FormData>;
  }

  export type RouteHandlerContext = {
    params: Record<string, string | string[]>;
  };
}


declare module "next" {
  export interface MetadataViewport {
    width?: string | number;
    initialScale?: number;
    maximumScale?: number;
    userScalable?: boolean;
    viewportFit?: string;
    [key: string]: unknown;
  }

  export interface AppleWebApp {
    capable?: boolean;
    statusBarStyle?: string;
    title?: string;
    [key: string]: unknown;
  }

  export interface Metadata {
    title?: string | { default: string; template?: string };
    description?: string;
    manifest?: string;
    themeColor?: string;
    appleWebApp?: AppleWebApp;
    icons?: Record<string, unknown>;
    viewport?: MetadataViewport;
    other?: Record<string, string>;
    [key: string]: unknown;
  }

  export function useRouter(): {
    push: (href: string) => void;
    replace: (href: string) => void;
    refresh: () => void;
  };

  export function usePathname(): string;
  export function useSearchParams(): URLSearchParams;
}

declare module "next/font/google" {
  export interface FontOptions {
    variable?: string;
    weight?: string | string[];
    subsets?: string[];
    display?: string;
    [key: string]: unknown;
  }
  export interface FontResult {
    variable: string;
    className?: string;
    style?: { fontFamily: string };
  }
  export function Geist(options: FontOptions): FontResult;
  export function Geist_Mono(options: FontOptions): FontResult;
  export function Inter(options: FontOptions): FontResult;
  export function Roboto(options: FontOptions): FontResult;
}

declare module "next/navigation" {
  export function useRouter(): {
    push: (href: string) => void;
    replace: (href: string) => void;
    refresh: () => void;
  };
  export function usePathname(): string;
  export function useSearchParams(): URLSearchParams;
}

declare module "next/link" {
  import * as React from "react";
  export interface LinkProps
    extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
    href: string;
    legacyBehavior?: boolean;
  }
  const Link: React.FC<LinkProps>;
  export default Link;
}

declare module "next/image" {
  import * as React from "react";
  export interface ImageProps
    extends React.ImgHTMLAttributes<HTMLImageElement> {
    src: string | unknown;
    alt: string;
    width?: number | string;
    height?: number | string;
    fill?: boolean;
    priority?: boolean;
  }
  const Image: React.FC<ImageProps>;
  export default Image;
}
