"use client"

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

interface MetricDataPoint {
  timestamp: string
  value: number
  label?: string
}

interface MetricsChartProps {
  data: MetricDataPoint[]
  title: string
  description?: string
  valueFormatter?: (value: number) => string
  color?: string
  type?: "area" | "bar"
}

export function MetricsChart({
  data,
  title,
  description,
  valueFormatter = (v) => v.toString(),
  color = "hsl(var(--primary))",
  type = "area",
}: MetricsChartProps) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center text-muted-foreground">
            No data available
          </div>
        </CardContent>
      </Card>
    )
  }

  const ChartComponent = type === "bar" ? BarChart : AreaChart
  const DataComponent = type === "bar" ? Bar : Area

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <ChartComponent
              data={data}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={valueFormatter}
                className="text-muted-foreground"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "var(--radius)",
                }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
                formatter={(value) => [valueFormatter(value as number), title]}
              />
              {type === "area" ? (
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  fill={color}
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              ) : (
                <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
              )}
            </ChartComponent>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

// Specialized chart for TTFT (Time to First Token)
export function TTFTChart({ data }: { data: Array<{ timestamp: string; ttft_ms: number }> }) {
  return (
    <MetricsChart
      data={data.map((d) => ({ timestamp: d.timestamp, value: d.ttft_ms }))}
      title="Time to First Token"
      description="Inference latency (ms)"
      valueFormatter={(v) => `${v.toFixed(0)}ms`}
      color="hsl(var(--chart-1))"
    />
  )
}

// Specialized chart for tokens per second
export function ThroughputChart({
  data,
}: {
  data: Array<{ timestamp: string; tokens_per_second: number }>
}) {
  return (
    <MetricsChart
      data={data.map((d) => ({ timestamp: d.timestamp, value: d.tokens_per_second }))}
      title="Inference Throughput"
      description="Tokens per second"
      valueFormatter={(v) => `${v.toFixed(1)} tok/s`}
      color="hsl(var(--chart-2))"
    />
  )
}

// Memory usage chart
export function MemoryChart({
  data,
}: {
  data: Array<{ timestamp: string; memory_gb: number }>
}) {
  return (
    <MetricsChart
      data={data.map((d) => ({ timestamp: d.timestamp, value: d.memory_gb }))}
      title="Memory Usage"
      description="GPU memory allocated"
      valueFormatter={(v) => `${v.toFixed(1)} GB`}
      color="hsl(var(--chart-3))"
      type="area"
    />
  )
}
