import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => {
  const location = useLocation();
  // Extract dataset ID from path if it exists (e.g. /dataset/123/stats)
  const pathParts = location.pathname.split('/');
  const datasetId = pathParts[1] === 'dataset' ? pathParts[2] : undefined;
  
  const showSidebar = location.pathname !== '/';

  return (
    <div className="min-h-screen bg-background flex flex-col overflow-hidden relative">
      {/* No animated mesh - stark contrast instead */}

      <Navbar />
      
      <div className="flex flex-1 overflow-hidden relative z-10 w-full max-w-[1600px] mx-auto">
        {showSidebar && <Sidebar datasetId={datasetId} />}
        
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
            <Outlet />
        </main>
      </div>
    </div>
  );
};
