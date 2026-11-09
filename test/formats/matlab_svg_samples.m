function matlab_svg_samples(outdir)
% MATLAB SVG samples for test/formats/test_svgimport.py, written into
% OUTDIR by print -dsvg (exportgraphics has no SVG before R2023).
%   matlab -batch "addpath('test/formats'); matlab_svg_samples('test/data/svgimport/matlab')"
set(groot, 'defaultFigureVisible', 'off');
if ~exist(outdir, 'dir'), mkdir(outdir); end
out = @(name) fullfile(outdir, [name '.svg']);

% lines, markers, legend, grid, TeX and LaTeX labels
f = figure; x = linspace(0, 2*pi, 200);
plot(x, sin(x), '-', x, cos(x), '--', x, sin(2*x), ':', 'LineWidth', 1.5);
hold on; plot(x(1:20:end), cos(x(1:20:end)), 'o', 'MarkerFaceColor', 'y');
xlabel('x (rad)'); ylabel('$f(x)=\sin x$', 'Interpreter', 'latex');
title('Line plot \alpha^2 + \beta_i');
legend('sin', 'cos', 'sin 2x', 'pts'); grid on;
print(f, '-dsvg', out('line')); close(f);

% scatter with a colormap
f = figure; rng(1);
scatter(randn(300, 1), randn(300, 1), 30, rand(300, 1), 'filled');
colorbar; title('scatter');
print(f, '-dsvg', out('scatter')); close(f);

% overlapping transparent patches
f = figure;
patch([0 1 1 0], [0 0 1 1], 'r', 'FaceAlpha', 0.5); hold on;
patch([0.5 1.5 1.5 0.5], [0.5 0.5 1.5 1.5], 'b', 'FaceAlpha', 0.5, ...
      'EdgeColor', 'g', 'LineWidth', 2);
axis equal; title('patches');
print(f, '-dsvg', out('patch')); close(f);

% image with a colorbar
f = figure; imagesc(peaks(40)); colorbar; axis image; title('imagesc');
print(f, '-dsvg', out('image')); close(f);

% surface
f = figure; surf(peaks(25)); shading faceted; title('surf');
print(f, '-dsvg', out('surf')); close(f);

% filled contours (nested regions)
f = figure; contourf(peaks(60), 10); colorbar; title('contourf');
print(f, '-dsvg', out('contourf')); close(f);

% bars and a text annotation
f = figure; bar([3 5 2; 4 1 6]);
text(1, 5.5, 'annotation', 'FontSize', 14, 'Color', 'm'); title('bars');
print(f, '-dsvg', out('bar')); close(f);
end
