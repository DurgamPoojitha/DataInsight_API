import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const DataCleaningPage: React.FC = () => {

  // In a real application, we might fetch a cleaning audit log from the backend.
  // For now, we simulate the standard automated cleaning pipeline executed by DataInsight API.
  const steps = [
    { title: 'Standardize Column Names', desc: 'Trimmed whitespace and converted to snake_case.' },
    { title: 'Handle Missing Values', desc: 'Imputed numeric nulls with median, categorical with mode.' },
    { title: 'Remove Duplicates', desc: 'Scanned entire dataset and removed exact duplicate rows.' },
    { title: 'Type Inference', desc: 'Automatically downcast numeric types to save memory.' },
  ];

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Automated Data Cleaning</h1>
        <p className="text-muted-foreground">The AI pipeline executed the following operations on your dataset.</p>
      </div>

      <div className="max-w-3xl glass-card p-8">
        <div className="relative border-l-2 border-primary/30 ml-6 pl-8 space-y-12">
          {steps.map((step, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.2 }}
              className="relative"
            >
              <div className="absolute -left-[45px] top-0 h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center border border-primary/50 text-primary">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div className="bg-white/5 p-6 rounded-xl border border-white/10 hover:bg-white/10 transition-colors">
                <h3 className="text-xl font-bold mb-2 text-foreground">{step.title}</h3>
                <p className="text-muted-foreground">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};
