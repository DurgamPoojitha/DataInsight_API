import React, { useCallback, useState } from 'react';
import { UploadCloud, FileSpreadsheet, Loader2, CheckCircle2, ArrowRight, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../lib/utils';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../services/api';
import { useNavigate } from 'react-router-dom';

export const UploadZone: React.FC = () => {
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post('/datasets/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data.data; // { dataset_id: string }
    },
    onSuccess: (data) => {
      // Small delay for the success animation
      setTimeout(() => {
        navigate(`/dataset/${data.dataset_id}`);
      }, 1500);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to upload dataset');
    }
  });

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    setError(null);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      if (file.name.endsWith('.csv')) {
        uploadMutation.mutate(file);
      } else {
        setError('Only .csv files are supported');
      }
    }
  }, [uploadMutation]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith('.csv')) {
        uploadMutation.mutate(file);
      } else {
        setError('Only .csv files are supported');
      }
    }
  };

  const isUploading = uploadMutation.isPending;
  const isSuccess = uploadMutation.isSuccess;

  return (
    <div className="w-full max-w-2xl mx-auto relative group">
      {/* Subtle glow effect behind the upload zone */}
      <div className="absolute -inset-1 bg-gradient-to-r from-primary/30 to-accent/30 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-1000"></div>
      
      <motion.div
        className={cn(
          "relative flex flex-col items-center justify-center w-full h-[320px] rounded-2xl border transition-all duration-300 overflow-hidden bg-card/80 backdrop-blur-md",
          isDragging ? "border-primary bg-primary/5 scale-[1.02]" : "border-border hover:border-border/80",
          (isUploading || isSuccess) && "pointer-events-none"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        whileHover={!isUploading && !isSuccess ? { scale: 1.01 } : {}}
        whileTap={!isUploading && !isSuccess ? { scale: 0.99 } : {}}
      >
        <input 
          type="file" 
          accept=".csv" 
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
          disabled={isUploading || isSuccess}
        />

        <AnimatePresence mode="wait">
          {!isUploading && !isSuccess && (
            <motion.div 
              key="idle"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col items-center z-0 pointer-events-none"
            >
              <div className="h-16 w-16 rounded-2xl bg-muted flex items-center justify-center mb-6 border border-border shadow-sm group-hover:bg-primary/10 group-hover:border-primary/20 transition-all duration-500">
                <UploadCloud className="h-7 w-7 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-foreground">Upload Dataset</h3>
              <p className="text-sm text-muted-foreground text-center max-w-[280px] leading-relaxed">
                Drag and drop your CSV file here, or click to browse files.
              </p>
              
              <div className="mt-8 flex items-center gap-2 text-xs font-medium text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-full border border-border">
                <FileSpreadsheet className="h-3.5 w-3.5" />
                Supports .csv files up to 50MB
              </div>
            </motion.div>
          )}

          {isUploading && (
            <motion.div 
              key="uploading"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.05 }}
              transition={{ duration: 0.3 }}
              className="flex flex-col items-center z-0 w-full px-12"
            >
              <div className="relative mb-8">
                <div className="absolute inset-0 rounded-full blur-md bg-primary/20 animate-pulse"></div>
                <div className="relative h-16 w-16 rounded-full bg-card border border-primary/30 flex items-center justify-center shadow-[0_0_15px_rgba(var(--primary),0.5)]">
                  <Loader2 className="h-7 w-7 text-primary animate-spin" />
                </div>
              </div>
              <h3 className="text-lg font-semibold mb-2 text-foreground">Processing Pipeline Active</h3>
              <p className="text-sm text-muted-foreground text-center animate-pulse">
                Extracting schema and generating statistical profile...
              </p>
              
              {/* Fake progress bar */}
              <div className="w-full h-1.5 bg-muted rounded-full mt-8 overflow-hidden">
                <motion.div 
                  initial={{ width: "0%" }}
                  animate={{ width: "80%" }}
                  transition={{ duration: 10, ease: "easeOut" }}
                  className="h-full bg-primary"
                />
              </div>
            </motion.div>
          )}

          {isSuccess && (
            <motion.div 
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, type: "spring" }}
              className="flex flex-col items-center z-0"
            >
              <div className="h-16 w-16 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6 border border-emerald-500/20">
                <CheckCircle2 className="h-8 w-8 text-emerald-500" />
              </div>
              <h3 className="text-xl font-semibold mb-2 text-foreground">Analysis Complete</h3>
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                Redirecting to dashboard <ArrowRight className="h-4 w-4 animate-pulse" />
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {error && (
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute -bottom-16 left-0 right-0 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive-foreground text-sm flex items-center justify-center shadow-lg backdrop-blur-md"
        >
          <AlertCircle className="mr-2 h-4 w-4" />
          <span className="font-medium">{error}</span>
        </motion.div>
      )}
    </div>
  );
};
