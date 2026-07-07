import React, { useCallback, useState } from 'react';
import { UploadCloud, FileSpreadsheet, Loader2, CheckCircle2 } from 'lucide-react';
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
      const res = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data; // { dataset_id: string }
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
    <div className="w-full max-w-3xl mx-auto">
      <motion.div
        className={cn(
          "relative flex flex-col items-center justify-center w-full h-80 rounded-3xl border-2 border-dashed transition-all duration-300 overflow-hidden",
          isDragging ? "border-primary bg-primary/10 scale-105" : "border-white/20 glass hover:border-primary/50 hover:bg-white/5",
          (isUploading || isSuccess) && "pointer-events-none"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        whileHover={!isUploading && !isSuccess ? { scale: 1.02 } : {}}
        whileTap={!isUploading && !isSuccess ? { scale: 0.98 } : {}}
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
              className="flex flex-col items-center z-0 pointer-events-none"
            >
              <div className="h-20 w-20 rounded-full bg-primary/20 flex items-center justify-center mb-6 border border-primary/30">
                <UploadCloud className="h-10 w-10 text-primary" />
              </div>
              <h3 className="text-2xl font-bold mb-2">Upload Dataset</h3>
              <p className="text-muted-foreground text-center max-w-md">
                Drag and drop your CSV file here, or click to browse. <br/>
                Our AI engine will process it instantly.
              </p>
            </motion.div>
          )}

          {isUploading && (
            <motion.div 
              key="uploading"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.2 }}
              className="flex flex-col items-center z-0"
            >
              <Loader2 className="h-16 w-16 text-primary animate-spin mb-6" />
              <h3 className="text-2xl font-bold mb-2">Analyzing Data...</h3>
              <p className="text-muted-foreground">Running statistical analysis and anomaly detection</p>
            </motion.div>
          )}

          {isSuccess && (
            <motion.div 
              key="success"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center z-0"
            >
              <div className="h-20 w-20 rounded-full bg-emerald-500/20 flex items-center justify-center mb-6 border border-emerald-500/30">
                <CheckCircle2 className="h-10 w-10 text-emerald-400" />
              </div>
              <h3 className="text-2xl font-bold mb-2 text-emerald-400">Analysis Complete!</h3>
              <p className="text-muted-foreground">Redirecting to your dashboard...</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {error && (
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 p-4 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive-foreground flex items-center"
        >
          <FileSpreadsheet className="mr-3 h-5 w-5" />
          <span>{error}</span>
        </motion.div>
      )}
    </div>
  );
};
