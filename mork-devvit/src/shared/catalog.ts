export type CatalogCard = {
  name: string;
  image: string;
  set: string;
  hcid?: string | number;
  tags?: string[];
  base_tags?: string[];
};

export type CatalogRoot = {
  data: CatalogCard[];
};
