import React from 'react';
import { UploadZone } from '../components/ui/UploadZone';
import { Database, FileText, Zap, HardDrive } from 'lucide-react';
import { motion } from 'framer-motion';

export const DashboardPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-10 pb-20">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-lg">Upload a new dataset or select a recent one below.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { title: "Datasets Uploaded", value: "24", icon: Database, color: "text-primary", bg: "bg-primary/20" },
          { title: "Reports Generated", value: "142", icon: FileText, color: "text-emerald-400", bg: "bg-emerald-500/20" },
          { title: "Avg. Processing Time", value: "1.2s", icon: Zap, color: "text-amber-400", bg: "bg-amber-500/20" },
          { title: "Storage Used", value: "1.4 GB", icon: HardDrive, color: "text-accent", bg: "bg-accent/20" },
        ].map((stat, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-card p-6 flex flex-col gap-4 group cursor-default"
          >
            <div className="flex justify-between items-start">
              <span className="text-muted-foreground font-medium">{stat.title}</span>
              <div className={`p-2 rounded-lg ${stat.bg} ${stat.color} transition-transform group-hover:scale-110`}>
                <stat.icon className="h-5 w-5" />
              </div>
            </div>
            <span className="text-4xl font-bold">{stat.value}</span>
          </motion.div>
        ))}
      </div>

      <section>
        <h2 className="text-2xl font-bold tracking-tight mb-6">New Analysis</h2>
        <UploadZone />
      </section>

    </div>
  );
};
