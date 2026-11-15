export type CatalogCard = {
  name: string;
  image: string;
  set: string;
  hcid?: string | number;
  tags?: string[];
  base_tags?: string[];
};

export type CatalogRoot = {
  /** Legacy Hellfall list payload. */
  data?: CatalogCard[];
  /** Pre-built cache payload (current GCS catalog.json). */
  idMap?: Record<string, CatalogCard>;
  nameMap?: unknown;
};
