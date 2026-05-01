// ─── CRS JSON shape (mirrors analyzer.py extraction schema) ──────────────────

export interface Page1Item {
  no: string;
  description: string;
  spec: string;
  review: string;
}

export interface Page2CostItem {
  no: string;
  description: string;
  value: string;
}

export interface Page2RiskItem {
  no: string;
  description: string;
  value: string;
}

export interface CRSData {
  customer_name: string;
  enquiry_ref: string;
  end_use: string;
  source_of_information: string;
  review_no: string | null;

  page1: Page1Item[];
  page2_cost: Page2CostItem[];
  page2_risk: Page2RiskItem[];
  concluding_remarks: string;
}

export interface PreviewResponse {
  filename: string;
  data: CRSData;
}

export type AnalysisStage =
  | "idle"
  | "uploading"
  | "analysing"
  | "done"
  | "error";
