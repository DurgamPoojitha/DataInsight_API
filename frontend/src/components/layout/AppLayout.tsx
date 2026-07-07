import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { motion } from 'framer-motion';

export const AppLayout: React.FC = () => {
  const location = useLocation();
  // Extract dataset ID from path if it exists (e.g. /dataset/123/stats)
  const pathParts = location.pathname.split('/');
  const datasetId = pathParts[1] === 'dataset' ? pathParts[2] : undefined;
  
  const showSidebar = location.pathname !== '/';

  return (
    <div className="min-h-screen bg-background flex flex-col overflow-hidden relative">
      {/* Animated background mesh */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[30%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/20 blur-[120px] mix-blend-screen opacity-50 animate-pulse" />
        <div className="absolute top-[20%] -right-[20%] w-[60%] h-[60%] rounded-full bg-accent/20 blur-[150px] mix-blend-screen opacity-40 animate-pulse delay-1000" />
        <div className="absolute -bottom-[20%] left-[20%] w-[50%] h-[50%] rounded-full bg-emerald-500/10 blur-[100px] mix-blend-screen opacity-30 animate-pulse delay-700" />
      </div>

      <Navbar />
      
      <div className="flex flex-1 overflow-hidden relative z-10">
        {showSidebar && <Sidebar datasetId={datasetId} />}
        
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="mx-auto max-w-7xl h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
};
