import { Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage } from './pages/DashboardPage';
import { DatasetSummaryPage } from './pages/DatasetSummaryPage';
import { StatisticsPage } from './pages/StatisticsPage';
import { VisualizationPage } from './pages/VisualizationPage';
import { MissingPage } from './pages/MissingPage';
import { OutliersPage } from './pages/OutliersPage';
import { ReportPage } from './pages/ReportPage';
import { DataCleaningPage } from './pages/DataCleaningPage';

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/dataset/:datasetId" element={<DatasetSummaryPage />} />
        <Route path="/dataset/:datasetId/cleaning" element={<DataCleaningPage />} />
        <Route path="/dataset/:datasetId/stats" element={<StatisticsPage />} />
        <Route path="/dataset/:datasetId/plots" element={<VisualizationPage />} />
        <Route path="/dataset/:datasetId/missing" element={<MissingPage />} />
        <Route path="/dataset/:datasetId/outliers" element={<OutliersPage />} />
        <Route path="/dataset/:datasetId/report" element={<ReportPage />} />
      </Route>
    </Routes>
  );
}

export default App;
