import api from "./client"

export const askPolicy = (question) =>
  api.post("/policy-qa", { question }).then(r => r.data)
