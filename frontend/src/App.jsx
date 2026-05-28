import { BrowserRouter, Routes, Route } from "react-router-dom"
import Layout from "./components/Layout"
import Dashboard from "./pages/Dashboard"
import Submissions from "./pages/Submissions"
import SubmissionDetail from "./pages/SubmissionDetail"
import NewSubmission from "./pages/NewSubmission"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="submissions" element={<Submissions />} />
          <Route path="submissions/:id" element={<SubmissionDetail />} />
          <Route path="new-submission" element={<NewSubmission />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
