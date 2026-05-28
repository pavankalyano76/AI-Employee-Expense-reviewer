import api from "./client"

export const getSubmissions     = (params)  => api.get("/submissions/", { params }).then(r => r.data)
export const getSubmission      = (id)      => api.get(`/submissions/${id}`).then(r => r.data)
export const createSubmission   = (payload) => api.post("/submissions/", payload).then(r => r.data)
export const reviewSubmission   = (id)      => api.post(`/submissions/${id}/review`).then(r => r.data)
export const overrideSubmission = (id, payload) =>
  api.post(`/submissions/${id}/override`, payload).then(r => r.data)

export const uploadReceipt = (submissionId, file) => {
  const form = new FormData()
  form.append("file", file)
  return api.post(`/submissions/${submissionId}/receipts`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then(r => r.data)
}
