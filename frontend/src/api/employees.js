import api from "./client"

export const getEmployee    = (employeeId) => api.get(`/employees/${employeeId}`).then(r => r.data)
export const createEmployee = (payload)    => api.post("/employees/", payload).then(r => r.data)

export const getOrCreateEmployee = async (payload) => {
  try {
    return await getEmployee(payload.employee_id)
  } catch (err) {
    if (err.response?.status === 404) {
      return await createEmployee(payload)
    }
    throw err
  }
}
