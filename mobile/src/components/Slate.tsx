/**
 * L'ardoise : zone de dessin libre pour poser ses calculs au doigt ou au stylet.
 *
 * Le trace est conserve sous forme **vectorielle** (listes de points) et non en
 * image : c'est leger a transmettre, redimensionnable, et le parent peut le
 * revoir tel quel dans son tableau de bord pour valider une réponse que la
 * reconnaissance n'a pas su lire.
 */

import { useMemo, useRef, useState } from "react";
import {
  PanResponder,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  type LayoutChangeEvent,
} from "react-native";
import Svg, { Line, Path } from "react-native-svg";

import { colors, radius, spacing, type } from "../theme";

export type StrokePath = number[][];

export interface SlateValue {
  paths: StrokePath[];
  width: number;
  height: number;
}

function toSvgPath(points: StrokePath): string {
  if (points.length === 0) return "";
  if (points.length === 1) {
    const [x, y] = points[0];
    return `M ${x} ${y} l 0.1 0`;
  }
  return points.reduce(
    (path, point, index) =>
      index === 0 ? `M ${point[0]} ${point[1]}` : `${path} L ${point[0]} ${point[1]}`,
    "",
  );
}

export function Slate({
  value,
  onChange,
  height = 260,
  showGrid = true,
}: {
  value: SlateValue | null;
  onChange: (value: SlateValue) => void;
  height?: number;
  showGrid?: boolean;
}) {
  const [width, setWidth] = useState(320);
  const paths = value?.paths ?? [];
  const currentRef = useRef<StrokePath>([]);
  const [current, setCurrent] = useState<StrokePath>([]);

  const responder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (event) => {
          const { locationX, locationY } = event.nativeEvent;
          currentRef.current = [[Math.round(locationX), Math.round(locationY)]];
          setCurrent(currentRef.current);
        },
        onPanResponderMove: (event) => {
          const { locationX, locationY } = event.nativeEvent;
          const point: number[] = [Math.round(locationX), Math.round(locationY)];
          const last = currentRef.current[currentRef.current.length - 1];
          // On ne conserve que les deplacements significatifs : trace plus leger.
          if (!last || Math.abs(last[0] - point[0]) + Math.abs(last[1] - point[1]) > 1.5) {
            currentRef.current = [...currentRef.current, point];
            setCurrent(currentRef.current);
          }
        },
        onPanResponderRelease: () => {
          if (currentRef.current.length > 0) {
            onChange({
              paths: [...paths, currentRef.current],
              width,
              height,
            });
          }
          currentRef.current = [];
          setCurrent([]);
        },
      }),
    [paths, onChange, width, height],
  );

  function onLayout(event: LayoutChangeEvent) {
    setWidth(Math.round(event.nativeEvent.layout.width));
  }

  function undo() {
    onChange({ paths: paths.slice(0, -1), width, height });
  }

  function clear() {
    onChange({ paths: [], width, height });
  }

  const gridLines = [];
  if (showGrid) {
    for (let y = 32; y < height; y += 32) {
      gridLines.push(<Line key={`h${y}`} x1={0} y1={y} x2={width} y2={y} stroke={colors.slateGrid} strokeWidth={1} />);
    }
    for (let x = 32; x < width; x += 32) {
      gridLines.push(<Line key={`v${x}`} x1={x} y1={0} x2={x} y2={height} stroke={colors.slateGrid} strokeWidth={1} />);
    }
  }

  return (
    <View>
      <View style={[styles.board, { height }]} onLayout={onLayout} {...responder.panHandlers}>
        <Svg width="100%" height={height}>
          {gridLines}
          {paths.map((path, index) => (
            <Path
              key={index}
              d={toSvgPath(path)}
              stroke={colors.slateInk}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          ))}
          {current.length > 0 && (
            <Path
              d={toSvgPath(current)}
              stroke={colors.slateInk}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          )}
        </Svg>
        {paths.length === 0 && current.length === 0 && (
          <View style={styles.placeholder} pointerEvents="none">
            <Text style={styles.placeholderText}>Pose ton calcul ici, au doigt ou au stylet.</Text>
          </View>
        )}
      </View>

      <View style={styles.tools}>
        <TouchableOpacity style={styles.tool} onPress={undo} disabled={paths.length === 0}>
          <Text style={[styles.toolText, paths.length === 0 && styles.toolDisabled]}>Annuler</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.tool} onPress={clear} disabled={paths.length === 0}>
          <Text style={[styles.toolText, paths.length === 0 && styles.toolDisabled]}>Tout effacer</Text>
        </TouchableOpacity>
        <View style={{ flex: 1 }} />
        <Text style={styles.hint}>
          {paths.length === 0 ? "" : `${paths.length} trait${paths.length > 1 ? "s" : ""}`}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  board: {
    backgroundColor: colors.slate,
    borderRadius: radius.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.line,
  },
  placeholder: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, alignItems: "center", justifyContent: "center" },
  placeholderText: { color: "#94a3b8", fontSize: 15 },
  tools: { flexDirection: "row", alignItems: "center", gap: spacing(1), marginTop: spacing(1) },
  tool: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: radius.sm, backgroundColor: colors.surface },
  toolText: { color: colors.ink, ...type.small },
  toolDisabled: { color: colors.inkFaint },
  hint: { color: colors.inkFaint, ...type.small },
});
