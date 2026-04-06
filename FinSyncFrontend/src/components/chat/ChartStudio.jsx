import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts';

const ChartStudio = ({ spec }) => {
  if (!spec || !Array.isArray(spec.data) || spec.data.length === 0) {
    return (
      <div className="rounded-xl border bg-muted/40 p-4 text-sm text-muted-foreground">
        Unable to render chart.
      </div>
    );
  }

  const chartType = spec.type || 'bar';

  const commonProps = {
    data: spec.data,
    margin: { top: 10, right: 16, left: 0, bottom: 0 },
  };

  const renderSeries = () => {
    const series = spec.series || [];
    if (chartType === 'line') {
      return series.map((serie, idx) => (
        <Line
          key={serie.field || idx}
          type="monotone"
          dataKey={serie.field}
          name={serie.label || serie.field}
          stroke={COLORS[idx % COLORS.length]}
          strokeWidth={2}
          dot={false}
        />
      ));
    }
    if (chartType === 'area') {
      return series.map((serie, idx) => (
        <Area
          key={serie.field || idx}
          type="monotone"
          dataKey={serie.field}
          name={serie.label || serie.field}
          stroke={COLORS[idx % COLORS.length]}
          fill={COLORS[idx % COLORS.length] + '55'}
        />
      ));
    }
    // default to bar
    return series.map((serie, idx) => (
      <Bar
        key={serie.field || idx}
        dataKey={serie.field}
        name={serie.label || serie.field}
        fill={COLORS[idx % COLORS.length]}
        stackId={chartType === 'stackedBar' ? 'stack' : undefined}
      />
    ));
  };

  const ChartComponent = chartType === 'line' ? LineChart : chartType === 'area' ? AreaChart : BarChart;

  return (
    <div className="rounded-2xl border bg-card p-4 shadow-sm">
      <div className="mb-3">
        <h3 className="text-base font-semibold text-foreground">{spec.title}</h3>
        {spec.description && (
          <p className="text-sm text-muted-foreground">{spec.description}</p>
        )}
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ChartComponent {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
            <XAxis dataKey={spec.x_axis?.field} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {renderSeries()}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
      {spec.metadata?.timeframe && (
        <p className="mt-3 text-xs text-muted-foreground">
          {spec.metadata.timeframe}
        </p>
      )}
    </div>
  );
};

const COLORS = [
  '#2563eb',
  '#7c3aed',
  '#0ea5e9',
  '#f97316',
  '#10b981',
  '#ef4444',
];

export default ChartStudio;
