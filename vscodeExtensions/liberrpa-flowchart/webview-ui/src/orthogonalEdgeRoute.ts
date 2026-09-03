// FileName: orthogonalEdgeRoute.ts

import type { LogicFlow } from "@logicflow/core";

export interface EdgeNodeBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

type SegmentAxis = "horizontal" | "vertical";
type AxisDirection = -1 | 1;
type EdgeEndpoint = "source" | "target";

interface SegmentDirection {
  axis: SegmentAxis;
  direction: AxisDirection;
}

interface EndpointSegmentDetail {
  direction: SegmentDirection;
  segmentLength: number;
  adjacentSegmentLength: number;
  visibleDistance: number;
}

interface PathScoreDetail {
  arrPoints: LogicFlow.Point[];
  floatScore: number;
}

const PREFERRED_ENDPOINT_SEGMENT_LENGTH = 30;
const PREFERRED_VISIBLE_ENDPOINT_DISTANCE = 20;
const MIN_ENDPOINT_SEGMENT_LENGTH = 10;
const ENDPOINT_SYMMETRY_TOLERANCE = 2;
const MIN_SYMMETRY_IMPROVEMENT = 4;
const MAX_PATH_LENGTH_RATIO = 1.5;
const MAX_PATH_LENGTH_INCREASE = 40;
const MAX_PATH_BOUNDS_EXPANSION = 30;
const MAX_PREFERRED_BEND_COUNT = 2;
const COORDINATE_EPSILON = 0.001;
const NODE_INTERIOR_EPSILON = 0.5;

export function optimizeEndpointBendSymmetry(
  arrPoints: LogicFlow.Point[],
  cornerRadius: number,
  arrNodeBounds: EdgeNodeBounds[] = [],
): LogicFlow.Point[] {
  const arrOriginalPoints = simplifyOrthogonalPath(arrPoints);
  if (arrOriginalPoints.length < 3) {
    return arrOriginalPoints;
  }

  const floatOriginalSymmetryDifference = calculateEndpointSymmetryDifference(
    arrOriginalPoints,
    cornerRadius,
  );
  if (
    floatOriginalSymmetryDifference <= ENDPOINT_SYMMETRY_TOLERANCE &&
    calculateBendCount(arrOriginalPoints) <= MAX_PREFERRED_BEND_COUNT
  ) {
    return arrOriginalPoints;
  }

  const arrCandidatePoints = generateSymmetricPathCandidates(
    arrOriginalPoints,
    cornerRadius,
  );
  const arrScoredCandidates: PathScoreDetail[] = [];

  for (const arrCandidate of arrCandidatePoints) {
    const arrSimplifiedCandidate = simplifyOrthogonalPath(arrCandidate);
    if (
      !isAcceptableCandidate(
        arrOriginalPoints,
        arrSimplifiedCandidate,
        cornerRadius,
        arrNodeBounds,
      )
    ) {
      continue;
    }

    arrScoredCandidates.push({
      arrPoints: arrSimplifiedCandidate,
      floatScore: calculateCandidateScore(
        arrOriginalPoints,
        arrSimplifiedCandidate,
        cornerRadius,
      ),
    });
  }

  arrScoredCandidates.sort(
    (candidateA, candidateB) => candidateA.floatScore - candidateB.floatScore,
  );

  return arrScoredCandidates[0]?.arrPoints ?? arrOriginalPoints;
}

function generateSymmetricPathCandidates(
  arrOriginalPoints: LogicFlow.Point[],
  cornerRadius: number,
): LogicFlow.Point[][] {
  // Prefer a route with no more than two bends.
  // A more complex original route remains available only when the compact candidates are not safe.
  const arrLowBendCandidates = generateLowBendPathCandidates(arrOriginalPoints);

  if (calculateBendCount(arrOriginalPoints) <= MAX_PREFERRED_BEND_COUNT) {
    return arrLowBendCandidates;
  }

  return arrLowBendCandidates.concat(
    generateTopologyPreservingCandidates(arrOriginalPoints, cornerRadius),
  );
}

function generateLowBendPathCandidates(
  arrOriginalPoints: LogicFlow.Point[],
): LogicFlow.Point[][] {
  const sourcePoint = arrOriginalPoints[0];
  const targetPoint = arrOriginalPoints[arrOriginalPoints.length - 1];
  const sourceDirection = getSegmentDirection(sourcePoint, arrOriginalPoints[1]);
  const targetDirection = getSegmentDirection(
    arrOriginalPoints[arrOriginalPoints.length - 2],
    targetPoint,
  );
  if (!sourceDirection || !targetDirection) {
    return [];
  }

  if (sourceDirection.axis !== targetDirection.axis) {
    // Perpendicular endpoint directions require either one bend or at least three.
    // Keep the compact one-bend topology instead of adding a symmetry dogleg.
    const cornerPoint =
      sourceDirection.axis === "horizontal"
        ? { x: targetPoint.x, y: sourcePoint.y }
        : { x: sourcePoint.x, y: targetPoint.y };

    return [[clonePoint(sourcePoint), cornerPoint, clonePoint(targetPoint)]];
  }

  return generateTwoBendPathCandidates(arrOriginalPoints, sourceDirection, targetDirection);
}

function generateTwoBendPathCandidates(
  arrOriginalPoints: LogicFlow.Point[],
  sourceDirection: SegmentDirection,
  targetDirection: SegmentDirection,
): LogicFlow.Point[][] {
  const sourcePoint = arrOriginalPoints[0];
  const targetPoint = arrOriginalPoints[arrOriginalPoints.length - 1];
  const sourceCoordinate = getAxisCoordinate(sourcePoint, sourceDirection.axis);
  const targetCoordinate = getAxisCoordinate(targetPoint, targetDirection.axis);
  const coordinateRange = getSharedRailCoordinateRange(
    sourceCoordinate,
    targetCoordinate,
    sourceDirection.direction,
    targetDirection.direction,
  );
  if (!coordinateRange) {
    return [];
  }

  const preferredSourceCoordinate =
    sourceCoordinate + sourceDirection.direction * PREFERRED_ENDPOINT_SEGMENT_LENGTH;
  const preferredTargetCoordinate =
    targetCoordinate - targetDirection.direction * PREFERRED_ENDPOINT_SEGMENT_LENGTH;
  const originalSourceRailCoordinate = getAxisCoordinate(
    arrOriginalPoints[1],
    sourceDirection.axis,
  );
  const originalTargetRailCoordinate = getAxisCoordinate(
    arrOriginalPoints[arrOriginalPoints.length - 2],
    targetDirection.axis,
  );
  const arrSharedRailCoordinates = getUniqueLengths(
    [
      (sourceCoordinate + targetCoordinate) / 2,
      (preferredSourceCoordinate + preferredTargetCoordinate) / 2,
      preferredSourceCoordinate,
      preferredTargetCoordinate,
      originalSourceRailCoordinate,
      originalTargetRailCoordinate,
      coordinateRange.minimum,
      coordinateRange.maximum,
    ]
      .filter(Number.isFinite)
      .map((coordinate) => clampCoordinate(coordinate, coordinateRange)),
  );

  return arrSharedRailCoordinates.map((sharedRailCoordinate) => {
    const sourceBendPoint = clonePoint(sourcePoint);
    const targetBendPoint = clonePoint(targetPoint);
    setAxisCoordinate(sourceBendPoint, sourceDirection.axis, sharedRailCoordinate);
    setAxisCoordinate(targetBendPoint, targetDirection.axis, sharedRailCoordinate);

    return [
      clonePoint(sourcePoint),
      sourceBendPoint,
      targetBendPoint,
      clonePoint(targetPoint),
    ];
  });
}

function getSharedRailCoordinateRange(
  sourceCoordinate: number,
  targetCoordinate: number,
  sourceDirection: AxisDirection,
  targetDirection: AxisDirection,
): { minimum: number; maximum: number } | null {
  let minimum = Number.NEGATIVE_INFINITY;
  let maximum = Number.POSITIVE_INFINITY;

  if (sourceDirection === 1) {
    minimum = Math.max(minimum, sourceCoordinate + MIN_ENDPOINT_SEGMENT_LENGTH);
  } else {
    maximum = Math.min(maximum, sourceCoordinate - MIN_ENDPOINT_SEGMENT_LENGTH);
  }

  if (targetDirection === 1) {
    maximum = Math.min(maximum, targetCoordinate - MIN_ENDPOINT_SEGMENT_LENGTH);
  } else {
    minimum = Math.max(minimum, targetCoordinate + MIN_ENDPOINT_SEGMENT_LENGTH);
  }

  if (minimum > maximum + COORDINATE_EPSILON) {
    return null;
  }

  return { minimum, maximum };
}

function clampCoordinate(
  coordinate: number,
  coordinateRange: { minimum: number; maximum: number },
): number {
  return Math.min(coordinateRange.maximum, Math.max(coordinateRange.minimum, coordinate));
}

function generateTopologyPreservingCandidates(
  arrOriginalPoints: LogicFlow.Point[],
  cornerRadius: number,
): LogicFlow.Point[][] {
  const sourceDetail = getEndpointSegmentDetail(arrOriginalPoints, cornerRadius, "source");
  const targetDetail = getEndpointSegmentDetail(arrOriginalPoints, cornerRadius, "target");
  if (!sourceDetail || !targetDetail) {
    return [];
  }

  const arrVisibleDistances = getCandidateVisibleDistances(
    sourceDetail.visibleDistance,
    targetDetail.visibleDistance,
  );
  const arrCandidatePoints: LogicFlow.Point[][] = [];

  for (const visibleDistance of arrVisibleDistances) {
    const sourceSegmentLength = calculateEndpointSegmentLength(
      visibleDistance,
      sourceDetail.adjacentSegmentLength,
      cornerRadius,
    );
    const targetSegmentLength = calculateEndpointSegmentLength(
      visibleDistance,
      targetDetail.adjacentSegmentLength,
      cornerRadius,
    );
    if (
      sourceSegmentLength < MIN_ENDPOINT_SEGMENT_LENGTH ||
      targetSegmentLength < MIN_ENDPOINT_SEGMENT_LENGTH
    ) {
      continue;
    }

    arrCandidatePoints.push(
      createTopologyPreservingCandidate(
        arrOriginalPoints,
        sourceDetail.direction,
        targetDetail.direction,
        sourceSegmentLength,
        targetSegmentLength,
      ),
    );
  }

  return arrCandidatePoints;
}

function createTopologyPreservingCandidate(
  arrOriginalPoints: LogicFlow.Point[],
  sourceDirection: SegmentDirection,
  targetDirection: SegmentDirection,
  sourceSegmentLength: number,
  targetSegmentLength: number,
): LogicFlow.Point[] {
  const arrCandidatePoints = clonePoints(arrOriginalPoints);
  const sourceBendPoint = movePoint(
    arrCandidatePoints[0],
    sourceDirection,
    sourceSegmentLength,
  );
  arrCandidatePoints[1] = sourceBendPoint;
  setAxisCoordinate(
    arrCandidatePoints[2],
    sourceDirection.axis,
    getAxisCoordinate(sourceBendPoint, sourceDirection.axis),
  );

  const intLastIndex = arrCandidatePoints.length - 1;
  const targetBendPoint = movePoint(
    arrCandidatePoints[intLastIndex],
    reverseDirection(targetDirection),
    targetSegmentLength,
  );
  arrCandidatePoints[intLastIndex - 1] = targetBendPoint;
  setAxisCoordinate(
    arrCandidatePoints[intLastIndex - 2],
    targetDirection.axis,
    getAxisCoordinate(targetBendPoint, targetDirection.axis),
  );

  return arrCandidatePoints;
}

function getCandidateVisibleDistances(
  sourceVisibleDistance: number,
  targetVisibleDistance: number,
): number[] {
  const minimumVisibleDistance = Math.min(sourceVisibleDistance, targetVisibleDistance);
  const maximumVisibleDistance = Math.max(sourceVisibleDistance, targetVisibleDistance);
  const preferredVisibleDistance = Math.min(
    maximumVisibleDistance,
    Math.max(minimumVisibleDistance, PREFERRED_VISIBLE_ENDPOINT_DISTANCE),
  );

  return getUniqueLengths([
    PREFERRED_VISIBLE_ENDPOINT_DISTANCE,
    preferredVisibleDistance,
    minimumVisibleDistance,
    maximumVisibleDistance,
  ]).filter((visibleDistance) => visibleDistance > COORDINATE_EPSILON);
}

function getUniqueLengths(arrLengths: number[]): number[] {
  const arrUniqueLengths: number[] = [];

  for (const length of arrLengths) {
    if (
      !arrUniqueLengths.some(
        (existingLength) => Math.abs(existingLength - length) <= COORDINATE_EPSILON,
      )
    ) {
      arrUniqueLengths.push(length);
    }
  }

  return arrUniqueLengths;
}

function calculateEndpointSegmentLength(
  visibleDistance: number,
  adjacentSegmentLength: number,
  cornerRadius: number,
): number {
  const maximumAppliedRadius = Math.min(adjacentSegmentLength / 2, cornerRadius);

  return visibleDistance <= maximumAppliedRadius
    ? visibleDistance * 2
    : visibleDistance + maximumAppliedRadius;
}

function isAcceptableCandidate(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
  cornerRadius: number,
  arrNodeBounds: EdgeNodeBounds[],
): boolean {
  if (
    arrCandidatePoints.length < 3 ||
    arePointListsEqual(arrOriginalPoints, arrCandidatePoints)
  ) {
    return false;
  }

  if (!isOrthogonalPath(arrCandidatePoints)) {
    return false;
  }

  if (!hasMatchingEndpoints(arrOriginalPoints, arrCandidatePoints)) {
    return false;
  }

  if (!hasMatchingEndpointDirections(arrOriginalPoints, arrCandidatePoints)) {
    return false;
  }

  if (hasNewSelfIntersection(arrOriginalPoints, arrCandidatePoints)) {
    return false;
  }

  if (
    arrNodeBounds.some((nodeBounds) =>
      doesPathCrossNodeInterior(arrCandidatePoints, nodeBounds),
    )
  ) {
    return false;
  }

  const intOriginalBendCount = calculateBendCount(arrOriginalPoints);
  const intCandidateBendCount = calculateBendCount(arrCandidatePoints);
  if (intCandidateBendCount > Math.max(MAX_PREFERRED_BEND_COUNT, intOriginalBendCount)) {
    return false;
  }

  if (!hasMinimumEndpointSegmentLength(arrCandidatePoints)) {
    return false;
  }

  const floatOriginalPathLength = calculatePathLength(arrOriginalPoints);
  const floatCandidatePathLength = calculatePathLength(arrCandidatePoints);
  const floatMaximumPathLength = Math.min(
    floatOriginalPathLength * MAX_PATH_LENGTH_RATIO,
    floatOriginalPathLength + MAX_PATH_LENGTH_INCREASE,
  );
  if (floatCandidatePathLength > floatMaximumPathLength + COORDINATE_EPSILON) {
    return false;
  }

  if (
    calculatePathBoundsExpansion(arrOriginalPoints, arrCandidatePoints) >
    MAX_PATH_BOUNDS_EXPANSION + COORDINATE_EPSILON
  ) {
    return false;
  }

  const floatOriginalSymmetryDifference = calculateEndpointSymmetryDifference(
    arrOriginalPoints,
    cornerRadius,
  );
  const floatCandidateSymmetryDifference = calculateEndpointSymmetryDifference(
    arrCandidatePoints,
    cornerRadius,
  );
  const floatSymmetryImprovement =
    floatOriginalSymmetryDifference - floatCandidateSymmetryDifference;
  // Reducing an excessive route to one or two bends takes priority as long as
  // endpoint symmetry is not made noticeably worse.
  const boolReducesToPreferredBendCount =
    intOriginalBendCount > MAX_PREFERRED_BEND_COUNT &&
    intCandidateBendCount <= MAX_PREFERRED_BEND_COUNT;

  if (boolReducesToPreferredBendCount) {
    return (
      floatCandidateSymmetryDifference <=
      floatOriginalSymmetryDifference + ENDPOINT_SYMMETRY_TOLERANCE
    );
  }

  return (
    floatCandidateSymmetryDifference <= ENDPOINT_SYMMETRY_TOLERANCE ||
    floatSymmetryImprovement >= MIN_SYMMETRY_IMPROVEMENT
  );
}

function hasMinimumEndpointSegmentLength(arrPoints: LogicFlow.Point[]): boolean {
  if (arrPoints.length < 3) {
    return true;
  }

  return (
    calculateSegmentLength(arrPoints[0], arrPoints[1]) >= MIN_ENDPOINT_SEGMENT_LENGTH &&
    calculateSegmentLength(
      arrPoints[arrPoints.length - 2],
      arrPoints[arrPoints.length - 1],
    ) >= MIN_ENDPOINT_SEGMENT_LENGTH
  );
}

function calculateCandidateScore(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
  cornerRadius: number,
): number {
  const floatSourceVisibleDistance = calculateEndpointVisibleDistance(
    arrCandidatePoints,
    cornerRadius,
    "source",
  );
  const floatTargetVisibleDistance = calculateEndpointVisibleDistance(
    arrCandidatePoints,
    cornerRadius,
    "target",
  );
  const floatSymmetryDifference = Math.abs(
    floatSourceVisibleDistance - floatTargetVisibleDistance,
  );
  const floatAverageVisibleDistance =
    (floatSourceVisibleDistance + floatTargetVisibleDistance) / 2;
  const floatAdditionalPathLength = Math.max(
    0,
    calculatePathLength(arrCandidatePoints) - calculatePathLength(arrOriginalPoints),
  );
  const intCandidateBendCount = calculateBendCount(arrCandidatePoints);
  const intExcessiveBendCount = Math.max(
    0,
    intCandidateBendCount - MAX_PREFERRED_BEND_COUNT,
  );
  const floatBoundsExpansion = calculatePathBoundsExpansion(
    arrOriginalPoints,
    arrCandidatePoints,
  );

  return (
    intExcessiveBendCount * 1_000_000 +
    intCandidateBendCount * 10_000 +
    floatSymmetryDifference * 1000 +
    Math.abs(floatAverageVisibleDistance - PREFERRED_VISIBLE_ENDPOINT_DISTANCE) * 5 +
    floatAdditionalPathLength * 2 +
    floatBoundsExpansion
  );
}

function calculateEndpointSymmetryDifference(
  arrPoints: LogicFlow.Point[],
  cornerRadius: number,
): number {
  return Math.abs(
    calculateEndpointVisibleDistance(arrPoints, cornerRadius, "source") -
      calculateEndpointVisibleDistance(arrPoints, cornerRadius, "target"),
  );
}

function calculateEndpointVisibleDistance(
  arrPoints: LogicFlow.Point[],
  cornerRadius: number,
  endpoint: EdgeEndpoint,
): number {
  return (
    getEndpointSegmentDetail(arrPoints, cornerRadius, endpoint)?.visibleDistance ??
    Number.POSITIVE_INFINITY
  );
}

function getEndpointSegmentDetail(
  arrPoints: LogicFlow.Point[],
  cornerRadius: number,
  endpoint: EdgeEndpoint,
): EndpointSegmentDetail | null {
  const intLastIndex = arrPoints.length - 1;
  const endpointStartPoint =
    endpoint === "source" ? arrPoints[0] : arrPoints[intLastIndex - 1];
  const endpointEndPoint = endpoint === "source" ? arrPoints[1] : arrPoints[intLastIndex];
  const adjacentStartPoint =
    endpoint === "source" ? arrPoints[1] : arrPoints[intLastIndex - 2];
  const adjacentEndPoint =
    endpoint === "source" ? arrPoints[2] : arrPoints[intLastIndex - 1];
  const direction = getSegmentDirection(endpointStartPoint, endpointEndPoint);
  const adjacentDirection = getSegmentDirection(adjacentStartPoint, adjacentEndPoint);
  if (!direction || !adjacentDirection || direction.axis === adjacentDirection.axis) {
    return null;
  }

  const segmentLength = calculateSegmentLength(endpointStartPoint, endpointEndPoint);
  const adjacentSegmentLength = calculateSegmentLength(
    adjacentStartPoint,
    adjacentEndPoint,
  );
  const appliedRadius = Math.min(
    segmentLength / 2,
    adjacentSegmentLength / 2,
    cornerRadius,
  );

  return {
    direction,
    segmentLength,
    adjacentSegmentLength,
    visibleDistance: segmentLength - appliedRadius,
  };
}

function simplifyOrthogonalPath(arrPoints: LogicFlow.Point[]): LogicFlow.Point[] {
  const arrSimplifiedPoints: LogicFlow.Point[] = [];

  for (const point of arrPoints) {
    const pointClone = clonePoint(point);
    const previousPoint = arrSimplifiedPoints[arrSimplifiedPoints.length - 1];
    if (previousPoint && arePointsEqual(previousPoint, pointClone)) {
      continue;
    }

    while (arrSimplifiedPoints.length >= 2) {
      const pointBeforePrevious = arrSimplifiedPoints[arrSimplifiedPoints.length - 2];
      const currentPreviousPoint = arrSimplifiedPoints[arrSimplifiedPoints.length - 1];
      if (!arePointsCollinear(pointBeforePrevious, currentPreviousPoint, pointClone)) {
        break;
      }
      arrSimplifiedPoints.pop();
    }

    arrSimplifiedPoints.push(pointClone);
  }

  return arrSimplifiedPoints;
}

function isOrthogonalPath(arrPoints: LogicFlow.Point[]): boolean {
  return arrPoints.every((point, index) => {
    if (index === 0) {
      return true;
    }
    return getSegmentDirection(arrPoints[index - 1], point) !== undefined;
  });
}

function hasMatchingEndpoints(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
): boolean {
  return (
    arePointsEqual(arrOriginalPoints[0], arrCandidatePoints[0]) &&
    arePointsEqual(
      arrOriginalPoints[arrOriginalPoints.length - 1],
      arrCandidatePoints[arrCandidatePoints.length - 1],
    )
  );
}

function hasMatchingEndpointDirections(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
): boolean {
  const originalSourceDirection = getSegmentDirection(
    arrOriginalPoints[0],
    arrOriginalPoints[1],
  );
  const candidateSourceDirection = getSegmentDirection(
    arrCandidatePoints[0],
    arrCandidatePoints[1],
  );
  const originalTargetDirection = getSegmentDirection(
    arrOriginalPoints[arrOriginalPoints.length - 2],
    arrOriginalPoints[arrOriginalPoints.length - 1],
  );
  const candidateTargetDirection = getSegmentDirection(
    arrCandidatePoints[arrCandidatePoints.length - 2],
    arrCandidatePoints[arrCandidatePoints.length - 1],
  );

  return (
    areDirectionsEqual(originalSourceDirection, candidateSourceDirection) &&
    areDirectionsEqual(originalTargetDirection, candidateTargetDirection)
  );
}

function areDirectionsEqual(
  directionA: SegmentDirection | undefined,
  directionB: SegmentDirection | undefined,
): boolean {
  return (
    directionA !== undefined &&
    directionB !== undefined &&
    directionA.axis === directionB.axis &&
    directionA.direction === directionB.direction
  );
}

function getSegmentDirection(
  pointA: LogicFlow.Point,
  pointB: LogicFlow.Point,
): SegmentDirection | undefined {
  if (Math.abs(pointA.y - pointB.y) <= COORDINATE_EPSILON) {
    const floatDeltaX = pointB.x - pointA.x;
    if (Math.abs(floatDeltaX) <= COORDINATE_EPSILON) {
      return undefined;
    }
    return {
      axis: "horizontal",
      direction: floatDeltaX > 0 ? 1 : -1,
    };
  }

  if (Math.abs(pointA.x - pointB.x) <= COORDINATE_EPSILON) {
    const floatDeltaY = pointB.y - pointA.y;
    if (Math.abs(floatDeltaY) <= COORDINATE_EPSILON) {
      return undefined;
    }
    return {
      axis: "vertical",
      direction: floatDeltaY > 0 ? 1 : -1,
    };
  }

  return undefined;
}

function reverseDirection(direction: SegmentDirection): SegmentDirection {
  return {
    axis: direction.axis,
    direction: direction.direction === 1 ? -1 : 1,
  };
}

function getAxisCoordinate(point: LogicFlow.Point, axis: SegmentAxis): number {
  return axis === "horizontal" ? point.x : point.y;
}

function setAxisCoordinate(
  point: LogicFlow.Point,
  axis: SegmentAxis,
  coordinate: number,
): void {
  if (axis === "horizontal") {
    point.x = coordinate;
  } else {
    point.y = coordinate;
  }
}

function movePoint(
  point: LogicFlow.Point,
  direction: SegmentDirection,
  distance: number,
): LogicFlow.Point {
  if (direction.axis === "horizontal") {
    return {
      x: point.x + direction.direction * distance,
      y: point.y,
    };
  }

  return {
    x: point.x,
    y: point.y + direction.direction * distance,
  };
}

function calculateSegmentLength(pointA: LogicFlow.Point, pointB: LogicFlow.Point): number {
  return Math.abs(pointA.x - pointB.x) + Math.abs(pointA.y - pointB.y);
}

function calculateBendCount(arrPoints: LogicFlow.Point[]): number {
  return Math.max(0, arrPoints.length - 2);
}

function calculatePathLength(arrPoints: LogicFlow.Point[]): number {
  let floatPathLength = 0;
  for (let index = 1; index < arrPoints.length; index += 1) {
    floatPathLength += calculateSegmentLength(arrPoints[index - 1], arrPoints[index]);
  }
  return floatPathLength;
}

function calculatePathBoundsExpansion(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
): number {
  const originalBounds = calculatePointBounds(arrOriginalPoints);
  const candidateBounds = calculatePointBounds(arrCandidatePoints);

  return Math.max(
    originalBounds.minX - candidateBounds.minX,
    candidateBounds.maxX - originalBounds.maxX,
    originalBounds.minY - candidateBounds.minY,
    candidateBounds.maxY - originalBounds.maxY,
    0,
  );
}

function calculatePointBounds(arrPoints: LogicFlow.Point[]): EdgeNodeBounds {
  return {
    minX: Math.min(...arrPoints.map((point) => point.x)),
    minY: Math.min(...arrPoints.map((point) => point.y)),
    maxX: Math.max(...arrPoints.map((point) => point.x)),
    maxY: Math.max(...arrPoints.map((point) => point.y)),
  };
}

function doesPathCrossNodeInterior(
  arrPoints: LogicFlow.Point[],
  nodeBounds: EdgeNodeBounds,
): boolean {
  for (let index = 1; index < arrPoints.length; index += 1) {
    if (doesSegmentCrossBoxInterior(arrPoints[index - 1], arrPoints[index], nodeBounds)) {
      return true;
    }
  }
  return false;
}

function doesSegmentCrossBoxInterior(
  pointA: LogicFlow.Point,
  pointB: LogicFlow.Point,
  nodeBounds: EdgeNodeBounds,
): boolean {
  if (Math.abs(pointA.y - pointB.y) <= COORDINATE_EPSILON) {
    if (
      pointA.y <= nodeBounds.minY + NODE_INTERIOR_EPSILON ||
      pointA.y >= nodeBounds.maxY - NODE_INTERIOR_EPSILON
    ) {
      return false;
    }

    return rangesOverlapInside(
      pointA.x,
      pointB.x,
      nodeBounds.minX + NODE_INTERIOR_EPSILON,
      nodeBounds.maxX - NODE_INTERIOR_EPSILON,
    );
  }

  if (Math.abs(pointA.x - pointB.x) <= COORDINATE_EPSILON) {
    if (
      pointA.x <= nodeBounds.minX + NODE_INTERIOR_EPSILON ||
      pointA.x >= nodeBounds.maxX - NODE_INTERIOR_EPSILON
    ) {
      return false;
    }

    return rangesOverlapInside(
      pointA.y,
      pointB.y,
      nodeBounds.minY + NODE_INTERIOR_EPSILON,
      nodeBounds.maxY - NODE_INTERIOR_EPSILON,
    );
  }

  return true;
}

function rangesOverlapInside(
  rangeStartA: number,
  rangeEndA: number,
  rangeStartB: number,
  rangeEndB: number,
): boolean {
  const floatOverlapStart = Math.max(Math.min(rangeStartA, rangeEndA), rangeStartB);
  const floatOverlapEnd = Math.min(Math.max(rangeStartA, rangeEndA), rangeEndB);
  return floatOverlapEnd - floatOverlapStart > COORDINATE_EPSILON;
}

function hasNewSelfIntersection(
  arrOriginalPoints: LogicFlow.Point[],
  arrCandidatePoints: LogicFlow.Point[],
): boolean {
  const setOriginalIntersections = getSelfIntersectionPairs(arrOriginalPoints);
  const setCandidateIntersections = getSelfIntersectionPairs(arrCandidatePoints);

  return [...setCandidateIntersections].some(
    (strIntersectionPair) => !setOriginalIntersections.has(strIntersectionPair),
  );
}

function getSelfIntersectionPairs(arrPoints: LogicFlow.Point[]): Set<string> {
  const setIntersectionPairs = new Set<string>();

  for (let firstIndex = 1; firstIndex < arrPoints.length; firstIndex += 1) {
    const firstStartPoint = arrPoints[firstIndex - 1];
    const firstEndPoint = arrPoints[firstIndex];

    for (
      let secondIndex = firstIndex + 2;
      secondIndex < arrPoints.length;
      secondIndex += 1
    ) {
      const secondStartPoint = arrPoints[secondIndex - 1];
      const secondEndPoint = arrPoints[secondIndex];
      if (
        doAxisAlignedSegmentsIntersect(
          firstStartPoint,
          firstEndPoint,
          secondStartPoint,
          secondEndPoint,
        )
      ) {
        setIntersectionPairs.add(`${firstIndex}:${secondIndex}`);
      }
    }
  }

  return setIntersectionPairs;
}

function doAxisAlignedSegmentsIntersect(
  firstStartPoint: LogicFlow.Point,
  firstEndPoint: LogicFlow.Point,
  secondStartPoint: LogicFlow.Point,
  secondEndPoint: LogicFlow.Point,
): boolean {
  const firstDirection = getSegmentDirection(firstStartPoint, firstEndPoint);
  const secondDirection = getSegmentDirection(secondStartPoint, secondEndPoint);
  if (!firstDirection || !secondDirection) {
    return true;
  }

  if (firstDirection.axis === secondDirection.axis) {
    if (firstDirection.axis === "horizontal") {
      return (
        Math.abs(firstStartPoint.y - secondStartPoint.y) <= COORDINATE_EPSILON &&
        rangesOverlapOrTouch(
          firstStartPoint.x,
          firstEndPoint.x,
          secondStartPoint.x,
          secondEndPoint.x,
        )
      );
    }

    return (
      Math.abs(firstStartPoint.x - secondStartPoint.x) <= COORDINATE_EPSILON &&
      rangesOverlapOrTouch(
        firstStartPoint.y,
        firstEndPoint.y,
        secondStartPoint.y,
        secondEndPoint.y,
      )
    );
  }

  const horizontalStartPoint =
    firstDirection.axis === "horizontal" ? firstStartPoint : secondStartPoint;
  const horizontalEndPoint =
    firstDirection.axis === "horizontal" ? firstEndPoint : secondEndPoint;
  const verticalStartPoint =
    firstDirection.axis === "vertical" ? firstStartPoint : secondStartPoint;
  const verticalEndPoint =
    firstDirection.axis === "vertical" ? firstEndPoint : secondEndPoint;

  return (
    isWithinClosedRange(
      verticalStartPoint.x,
      horizontalStartPoint.x,
      horizontalEndPoint.x,
    ) &&
    isWithinClosedRange(horizontalStartPoint.y, verticalStartPoint.y, verticalEndPoint.y)
  );
}

function rangesOverlapOrTouch(
  rangeStartA: number,
  rangeEndA: number,
  rangeStartB: number,
  rangeEndB: number,
): boolean {
  return (
    Math.max(Math.min(rangeStartA, rangeEndA), Math.min(rangeStartB, rangeEndB)) <=
    Math.min(Math.max(rangeStartA, rangeEndA), Math.max(rangeStartB, rangeEndB)) +
      COORDINATE_EPSILON
  );
}

function isWithinClosedRange(value: number, rangeStart: number, rangeEnd: number): boolean {
  return (
    value >= Math.min(rangeStart, rangeEnd) - COORDINATE_EPSILON &&
    value <= Math.max(rangeStart, rangeEnd) + COORDINATE_EPSILON
  );
}

function arePointListsEqual(
  arrPointsA: LogicFlow.Point[],
  arrPointsB: LogicFlow.Point[],
): boolean {
  return (
    arrPointsA.length === arrPointsB.length &&
    arrPointsA.every((point, index) => arePointsEqual(point, arrPointsB[index]))
  );
}

function arePointsEqual(pointA: LogicFlow.Point, pointB: LogicFlow.Point): boolean {
  return (
    Math.abs(pointA.x - pointB.x) <= COORDINATE_EPSILON &&
    Math.abs(pointA.y - pointB.y) <= COORDINATE_EPSILON
  );
}

function arePointsCollinear(
  pointA: LogicFlow.Point,
  pointB: LogicFlow.Point,
  pointC: LogicFlow.Point,
): boolean {
  return (
    (Math.abs(pointA.x - pointB.x) <= COORDINATE_EPSILON &&
      Math.abs(pointB.x - pointC.x) <= COORDINATE_EPSILON) ||
    (Math.abs(pointA.y - pointB.y) <= COORDINATE_EPSILON &&
      Math.abs(pointB.y - pointC.y) <= COORDINATE_EPSILON)
  );
}

function clonePoints(arrPoints: LogicFlow.Point[]): LogicFlow.Point[] {
  return arrPoints.map(clonePoint);
}

function clonePoint(point: LogicFlow.Point): LogicFlow.Point {
  return { ...point };
}
