import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'

function BouncingCat() {
  const [position, setPosition] = useState({ x: 100, y: 100 })
  const [velocity, setVelocity] = useState({ x: 2, y: 1.5 })
  const [rotation, setRotation] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const catSize = 80

  useEffect(() => {
    const animate = () => {
      setPosition((pos) => {
        const container = containerRef.current?.parentElement
        if (!container) return pos

        const maxX = container.clientWidth - catSize
        const maxY = container.clientHeight - catSize

        let newX = pos.x + velocity.x
        let newY = pos.y + velocity.y
        let newVelX = velocity.x
        let newVelY = velocity.y

        // Bounce off walls
        if (newX <= 0 || newX >= maxX) {
          newVelX = -velocity.x
          newX = newX <= 0 ? 0 : maxX
        }
        if (newY <= 0 || newY >= maxY) {
          newVelY = -velocity.y
          newY = newY <= 0 ? 0 : maxY
        }

        if (newVelX !== velocity.x || newVelY !== velocity.y) {
          setVelocity({ x: newVelX, y: newVelY })
        }

        return { x: newX, y: newY }
      })

      setRotation((r) => (r + 1) % 360)
    }

    const interval = setInterval(animate, 16)
    return () => clearInterval(interval)
  }, [velocity])

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-hidden pointer-events-none">
      <img
        src="/libix.svg"
        alt=""
        className="absolute opacity-20"
        style={{
          width: catSize,
          height: catSize,
          left: position.x,
          top: position.y,
          transform: `rotate(${rotation}deg)`,
        }}
      />
    </div>
  )
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await login(username, password)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Login failed',
        description: error instanceof Error ? error.message : 'Invalid credentials',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <BouncingCat />
      <Card className="relative z-10 w-[350px]">
        <CardHeader>
          <CardTitle>Libix</CardTitle>
          <CardDescription>Sign in to your account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
