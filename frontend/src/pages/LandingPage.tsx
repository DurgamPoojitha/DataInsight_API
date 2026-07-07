import React from 'react';
import { motion } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { Database, Sparkles, ShieldCheck, Zap } from 'lucide-react';
import { UploadZone } from '../components/ui/UploadZone';

export const LandingPage: React.FC = () => {

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 100 } },
  };

  return (
    <div className="flex flex-col items-center min-h-[calc(100vh-3.5rem)] relative overflow-hidden bg-background pt-16 md:pt-24 pb-20">
      
      {/* Background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] opacity-20 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/40 to-transparent blur-3xl rounded-full mix-blend-screen" />
      </div>

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="z-10 flex flex-col items-center text-center max-w-[900px] px-6 w-full"
      >
        <motion.div variants={itemVariants} className="mb-8 inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary/90">
          <Sparkles className="mr-2 h-3.5 w-3.5" />
          <span>DataInsight 2.0 Engine is live</span>
        </motion.div>
        
        <motion.h1 variants={itemVariants} className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-foreground leading-[1.1]">
          The intelligence layer <br className="hidden md:block" />
          for your raw data.
        </motion.h1>

        <motion.p variants={itemVariants} className="text-lg md:text-xl text-muted-foreground mb-12 max-w-2xl leading-relaxed font-medium">
          Upload any CSV and instantly receive automated cleaning, statistical profiling, correlation heatmaps, and downloadable reports. No code required.
        </motion.p>

        {/* Upload Zone directly on the landing page */}
        <motion.div variants={itemVariants} className="w-full max-w-2xl mb-24">
          <UploadZone />
        </motion.div>

        {/* Feature Grid */}
        <motion.div variants={containerVariants} className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-5xl mt-8">
          {[
            { icon: Database, title: 'Intelligent Parsing', desc: 'Automatically infers schema, detects missing values, and identifies anomalies.' },
            { icon: Zap, title: 'Instant Analytics', desc: 'Generates deep statistical profiles and rich interactive visualizations in milliseconds.' },
            { icon: ShieldCheck, title: 'Enterprise Secure', desc: 'Your data is processed ephemerally. Nothing is retained or used for model training.' }
          ].map((feature, i) => (
            <motion.div key={i} variants={itemVariants} className="text-left flex flex-col items-start">
              <div className="h-10 w-10 rounded-lg bg-muted border border-border flex items-center justify-center mb-4">
                <feature.icon className="h-5 w-5 text-foreground" />
              </div>
              <h3 className="text-base font-semibold mb-2 text-foreground">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.desc}</p>
            </motion.div>
          ))}
        </motion.div>

      </motion.div>
    </div>
  );
};
