"use client";

import { useState, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Download,
  Upload,
  FileJson,
  FileText,
  Loader2,
  CheckCircle,
  AlertCircle,
  FolderDown,
  FolderUp,
} from "lucide-react";
import { exportContent, importContent, type ContentType, type ImportResult } from "@/lib/api";

type ExportFormat = "json" | "markdown";

export default function ExportPage() {
  // Export state
  const [exportFormat, setExportFormat] = useState<ExportFormat>("json");
  const [exportNamespace, setExportNamespace] = useState("");
  const [exportContentType, setExportContentType] = useState<ContentType | "">("");
  const [includeChunks, setIncludeChunks] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Import state
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportContent({
        format: exportFormat,
        namespace: exportNamespace || undefined,
        content_type: exportContentType || undefined,
        include_chunks: includeChunks,
      });

      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kas-export-${new Date().toISOString().split("T")[0]}.${exportFormat === "json" ? "json" : "md"}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success("Export completed successfully");
    } catch (error) {
      console.error("Export failed:", error);
      toast.error("Failed to export content");
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportResult(null);

    try {
      const result = await importContent(file);
      setImportResult(result);

      if (result.errors.length === 0) {
        toast.success(`Imported ${result.imported} items successfully`);
      } else {
        toast.warning(`Imported ${result.imported} items with ${result.errors.length} errors`);
      }
    } catch (error) {
      console.error("Import failed:", error);
      toast.error("Failed to import content");
    } finally {
      setImporting(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const contentTypes: Array<{ value: ContentType | ""; label: string }> = [
    { value: "", label: "All Types" },
    { value: "note", label: "Notes" },
    { value: "bookmark", label: "Bookmarks" },
    { value: "youtube", label: "YouTube" },
    { value: "pdf", label: "PDFs" },
    { value: "file", label: "Files" },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FolderDown className="h-6 w-6" />
          Export & Import
        </h1>
        <p className="text-muted-foreground">
          Backup your knowledge base or restore from a previous export
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Export Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Download className="h-5 w-5" />
              Export Content
            </CardTitle>
            <CardDescription>
              Download your knowledge base content
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Format Selection */}
            <div>
              <label className="text-sm font-medium mb-2 block">Format</label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={exportFormat === "json" ? "default" : "outline"}
                  onClick={() => setExportFormat("json")}
                  className="flex-1 gap-2"
                >
                  <FileJson className="h-4 w-4" />
                  JSON
                </Button>
                <Button
                  type="button"
                  variant={exportFormat === "markdown" ? "default" : "outline"}
                  onClick={() => setExportFormat("markdown")}
                  className="flex-1 gap-2"
                >
                  <FileText className="h-4 w-4" />
                  Markdown
                </Button>
              </div>
            </div>

            {/* Namespace Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">
                Namespace (optional)
              </label>
              <Input
                placeholder="e.g., projects/my-project"
                value={exportNamespace}
                onChange={(e) => setExportNamespace(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Leave empty to export all namespaces
              </p>
            </div>

            {/* Content Type Filter */}
            <div>
              <label className="text-sm font-medium mb-2 block">
                Content Type
              </label>
              <div className="flex flex-wrap gap-2">
                {contentTypes.map((type) => (
                  <Button
                    key={type.value}
                    type="button"
                    variant={exportContentType === type.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => setExportContentType(type.value)}
                  >
                    {type.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Include Chunks Toggle */}
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <div>
                <p className="font-medium text-sm">Include Chunks</p>
                <p className="text-xs text-muted-foreground">
                  Export with all indexed text segments
                </p>
              </div>
              <Button
                type="button"
                variant={includeChunks ? "default" : "outline"}
                size="sm"
                onClick={() => setIncludeChunks(!includeChunks)}
              >
                {includeChunks ? "Yes" : "No"}
              </Button>
            </div>

            <Separator />

            <Button
              onClick={handleExport}
              disabled={exporting}
              className="w-full gap-2"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Export Knowledge Base
            </Button>
          </CardContent>
        </Card>

        {/* Import Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Import Content
            </CardTitle>
            <CardDescription>
              Restore content from a previous export
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border-2 border-dashed rounded-lg p-8 text-center">
              <FolderUp className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="font-medium mb-2">
                {importing ? "Importing..." : "Drop your export file here"}
              </p>
              <p className="text-sm text-muted-foreground mb-4">
                Supports JSON export files
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
                id="import-file"
              />
              <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
                className="gap-2"
              >
                {importing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                Select File
              </Button>
            </div>

            {/* Import Result */}
            {importResult && (
              <div className="space-y-3">
                <Separator />
                <div className="p-4 rounded-lg bg-muted/50">
                  <div className="flex items-center gap-2 mb-3">
                    {importResult.errors.length === 0 ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-yellow-500" />
                    )}
                    <span className="font-medium">Import Complete</span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold text-green-500">
                        {importResult.imported}
                      </p>
                      <p className="text-xs text-muted-foreground">Imported</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-yellow-500">
                        {importResult.skipped}
                      </p>
                      <p className="text-xs text-muted-foreground">Skipped</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-red-500">
                        {importResult.errors.length}
                      </p>
                      <p className="text-xs text-muted-foreground">Errors</p>
                    </div>
                  </div>
                  {importResult.errors.length > 0 && (
                    <div className="mt-4">
                      <p className="text-sm font-medium mb-2">Errors:</p>
                      <div className="max-h-32 overflow-y-auto space-y-1">
                        {importResult.errors.map((error, i) => (
                          <p key={i} className="text-xs text-red-500">
                            {error}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Info */}
            <div className="p-4 rounded-lg border bg-muted/30">
              <h4 className="font-medium text-sm mb-2">Import Notes</h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• Duplicate content will be skipped</li>
                <li>• Only JSON format is supported for import</li>
                <li>• Large imports may take several minutes</li>
                <li>• Existing content will not be modified</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
