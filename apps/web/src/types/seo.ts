export interface SEOConfig {
  title: string;
  titleTemplate?: string;
  description: string;
  keywords?: string[];
  canonical?: string;
  noindex?: boolean;  // 控制是否索引此页面
  og?: {
    type?: string;
    image?: string;
    title?: string;
    description?: string;
  };
  schema?: {
    '@type'?: string;
    [key: string]: unknown;
  };
}

export interface SEOPageConfig {
  zh: SEOConfig;
  en: SEOConfig;
}
