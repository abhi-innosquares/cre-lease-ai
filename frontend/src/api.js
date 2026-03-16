import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000"
});

export const getPortfolio = () =>
  API.get("/portfolio/summary");

export const getPortfolioAnalytics = () =>
  API.get("/analytics/portfolio");

export const askPortfolioQuestion = (payload) =>
  API.post("/chat/portfolio", payload);

export const getGreeting = () =>
  API.get("/chat/greeting");

export const askLeaseQuestion = (payload) =>
  API.post("/chat", payload);

export const getAllLeaseAnalytics = () =>
  API.get("/analytics/leases");

export const getPresignedUrl = (filename) =>
  API.get("/upload/presigned", { params: { filename } });

export const triggerProcessing = (files) =>
  API.post("/upload/process", { files });

export const getJobStatus = (jobId) =>
  API.get(`/upload/process/${jobId}`);

export const searchLeases = (params) =>
  API.get("/leases/search", { params });

export const getLeaseDocumentLink = (leaseId) =>
  API.get(`/leases/${leaseId}/document-link`);
