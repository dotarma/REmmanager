using System.Numerics;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Hosting;
using Windows.UI.ViewManagement;

namespace REmmanager;

static class Motion
{
    public static bool Reduced { get; set; }
    public static double Speed { get; set; } = 1;
    public static bool Enabled => !Reduced && new UISettings().AnimationsEnabled;

    // Material 3 Expressive tokens mapped to Windows Composition (unit-mass spring).
    // Source: AndroidX ExpressiveMotionTokens, v0_14_0. Spatial may overshoot;
    // critically damped effects remain monotonic.
    private const float DefaultSpatialDamping = 0.8f, DefaultSpatialStiffness = 380;
    private const float FastSpatialDamping = 0.6f, FastSpatialStiffness = 800;
    private const float DefaultEffectsStiffness = 1600;
    private static TimeSpan Period(float stiffness) => TimeSpan.FromSeconds(2 * Math.PI / Math.Sqrt(stiffness) / Speed);
    public static void Enter(FrameworkElement element, bool expressive = false)
    {
        var visual = ElementCompositionPreview.GetElementVisual(element);
        if (!Enabled) { visual.StopAnimation("Offset"); visual.StopAnimation("Opacity"); visual.Offset = Vector3.Zero; visual.Opacity = 1; return; }
        visual.Offset = new Vector3(0, expressive ? 20 : 10, 0);
        var spatial = visual.Compositor.CreateSpringVector3Animation();
        spatial.FinalValue = Vector3.Zero;
        spatial.DampingRatio = expressive ? DefaultSpatialDamping : FastSpatialDamping;
        spatial.Period = Period(expressive ? DefaultSpatialStiffness : FastSpatialStiffness);
        visual.StartAnimation("Offset", spatial);
        var effect = visual.Compositor.CreateScalarKeyFrameAnimation();
        // Analytic critically damped spring: x(t)=1-(1+omega*t)*exp(-omega*t).
        double omega = Math.Sqrt(DefaultEffectsStiffness);
        for (int i = 0; i <= 30; i++)
        {
            double t = i / 30.0 * 0.22;
            effect.InsertKeyFrame(i / 30f, (float)(1 - (1 + omega * t) * Math.Exp(-omega * t)));
        }
        effect.InsertKeyFrame(1, 1);
        effect.Duration = TimeSpan.FromMilliseconds(220 / Speed);
        visual.StartAnimation("Opacity", effect);
    }

    public static void WirePress(Button button)
    {
        button.PointerPressed += (_, _) => Scale(button, 0.97f, true);
        button.PointerReleased += (_, _) => Scale(button, 1, false);
        button.PointerExited += (_, _) => Scale(button, 1, false);
        button.LosingFocus += (_, _) => Scale(button, 1, false);
    }

    private static void Scale(FrameworkElement element, float target, bool pressed)
    {
        var visual = ElementCompositionPreview.GetElementVisual(element);
        visual.CenterPoint = new Vector3((float)element.ActualWidth / 2, (float)element.ActualHeight / 2, 0);
        if (!Enabled) { visual.StopAnimation("Scale"); visual.Scale = Vector3.One; return; }
        var spring = visual.Compositor.CreateSpringVector3Animation();
        spring.FinalValue = new Vector3(target, target, 1);
        spring.DampingRatio = pressed ? 1f : FastSpatialDamping;
        spring.Period = Period(FastSpatialStiffness);
        visual.StartAnimation("Scale", spring);
    }
}
