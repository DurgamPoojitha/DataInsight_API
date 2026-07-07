import React from 'react';
import { UploadZone } from '../components/ui/UploadZone';
import { Database, FileText, Zap, HardDrive, ArrowUpRight } from 'lucide-react';
import { motion } from 'framer-motion';

export const DashboardPage: React.FC = () => {
  return (
    <div className="flex flex-col gap-10 pb-20 pt-4 max-w-[1400px] mx-auto w-full">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Overview</h1>
        <p className="text-muted-foreground text-sm font-medium">System telemetry and active workspaces.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { title: "Datasets Analyzed", value: "24", icon: Database },
          { title: "Reports Generated", value: "142", icon: FileText },
          { title: "Avg. Latency", value: "1.2s", icon: Zap },
          { title: "Storage Consumed", value: "1.4 GB", icon: HardDrive },
        ].map((stat, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="rounded-xl border border-border bg-card p-5 flex flex-col gap-3 group cursor-default hover:border-border/80 transition-colors"
          >
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{stat.title}</span>
              <stat.icon className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
            </div>
            <span className="text-3xl font-bold text-foreground">{stat.value}</span>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-4">
        <section className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight text-foreground">New Workspace</h2>
          </div>
          <div className="rounded-xl border border-border bg-card p-8 flex items-center justify-center min-h-[360px]">
            <UploadZone />
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight text-foreground">Recent Activity</h2>
          </div>
          <div className="rounded-xl border border-border bg-card flex flex-col overflow-hidden">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="p-4 border-b border-border/50 flex gap-3 hover:bg-muted/30 transition-colors cursor-pointer group">
                <div className="h-8 w-8 rounded bg-muted flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                  <Database className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
                <div className="flex flex-col flex-1 min-w-0">
                  <span className="text-sm font-medium text-foreground truncate">sales_data_q{i}_2025.csv</span>
                  <span className="text-xs text-muted-foreground">Processed {i} hours ago</span>
                </div>
                <ArrowUpRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-foreground transition-colors self-center" />
              </div>
            ))}
          </div>
        </section>
      </div>

    </div>
  );
};
