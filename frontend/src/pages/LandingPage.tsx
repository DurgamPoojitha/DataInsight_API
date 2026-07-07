import React from 'react';
import { motion } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { ArrowRight, BarChart2, Database, Zap, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 100 } },
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-6rem)] relative overflow-hidden">
      
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="z-10 flex flex-col items-center text-center max-w-4xl px-6"
      >
        <motion.div variants={itemVariants} className="mb-6 inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm font-medium text-primary backdrop-blur-sm">
          <Zap className="mr-2 h-4 w-4" />
          <span>DataInsight AI v1.0 is now live</span>
        </motion.div>
        
        <motion.h1 variants={itemVariants} className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8">
          Transform Raw Data into <br className="hidden md:block" />
          <span className="text-gradient">Actionable Intelligence</span>
        </motion.h1>

        <motion.p variants={itemVariants} className="text-lg md:text-xl text-muted-foreground mb-12 max-w-2xl leading-relaxed">
          Upload any CSV and receive automated cleaning, statistical analysis, visualizations, correlation insights, anomaly detection, and downloadable reports.
        </motion.p>

        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-4 mb-20">
          <button 
            onClick={() => navigate('/dashboard')}
            className="group relative inline-flex items-center justify-center overflow-hidden rounded-xl bg-gradient-to-tr from-primary to-accent px-8 py-4 font-semibold text-white shadow-[0_0_40px_rgba(124,58,237,0.4)] transition-all hover:shadow-[0_0_60px_rgba(124,58,237,0.6)] hover:scale-105"
          >
            <span className="mr-2 text-lg">Start Analysis</span>
            <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
            <div className="absolute inset-0 h-full w-full bg-white/20 opacity-0 transition-opacity group-hover:opacity-100 mix-blend-overlay" />
          </button>
          
          <button className="inline-flex items-center justify-center rounded-xl border border-white/10 glass px-8 py-4 font-semibold text-foreground transition-all hover:bg-white/10 hover:scale-105">
            <span className="text-lg">View Demo</span>
          </button>
        </motion.div>

        {/* Feature grid */}
        <motion.div variants={containerVariants} className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl">
          {[
            { icon: Database, title: 'Smart Cleaning', desc: 'Automatically detect and fix missing values, outliers, and duplicates.' },
            { icon: BarChart2, title: 'Deep Analytics', desc: 'Generate instant statistical profiles and correlation heatmaps.' },
            { icon: ShieldCheck, title: 'Secure & Private', desc: 'Your data is processed ephemerally and never used to train models.' }
          ].map((feature, i) => (
            <motion.div key={i} variants={itemVariants} className="glass-card p-6 text-left group hover:-translate-y-2 transition-transform duration-300 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="h-12 w-12 rounded-lg bg-primary/20 flex items-center justify-center mb-4 border border-primary/30">
                <feature.icon className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-bold mb-2">{feature.title}</h3>
              <p className="text-muted-foreground">{feature.desc}</p>
            </motion.div>
          ))}
        </motion.div>

      </motion.div>
    </div>
  );
};
